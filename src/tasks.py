from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import hashlib
from .models import Article
from .scrapers import ScrapingService
from .llm_service import LLMService
from .email_service import EmailNotificationService

logger = logging.getLogger('news')


def hash_url(url: str) -> str:
    """Generate SHA-256 hash of the URL for duplicate detection."""
    from urllib.parse import urlparse, urlunparse
    
    # Normalize URL to handle variations
    parsed = urlparse(url)
    # Remove trailing slash, normalize scheme and netloc
    normalized_url = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip('/') or '/',
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    
    return hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()


@shared_task
def scrape_articles_task():
    """Celery task to scrape articles from all sources."""
    logger.info("=== CELERY TASK STARTED ===")
    logger.info("Starting article scraping task")
    
    try:
        # Initialize services
        logger.info("Initializing scraping and LLM services...")
        scraping_service = ScrapingService()
        llm_service = LLMService()
        
        # Scrape articles from all sources
        logger.info("Starting to scrape articles from all sources...")
        scraped_articles = scraping_service.scrape_all_sources()
        logger.info(f"Found {len(scraped_articles)} articles to process haha")
        
        # Check how many already exist in database
        existing_count = 0
        for article_data in scraped_articles:
            url_hash = hash_url(article_data['url'])
            logger.info(f"Checking if article already exists: {article_data['url']}")
            logger.info(f"Checking if article hashed url already exists: {url_hash}")
            if Article.objects.filter(hashed_url=url_hash).exists():
                logger.info(f"Article with hashed url = {url_hash} already exists")
                existing_count += 1
        
        logger.info(f"Articles found: {len(scraped_articles)}, Already in database: {existing_count}, New articles: {len(scraped_articles) - existing_count}")
        
        new_articles_count = 0
        new_article_ids = []
        
        # First pass: Create all new articles
        for i, article_data in enumerate(scraped_articles, 1):
            try:
                # Safely encode title for logging
                title = article_data['title'][:50] + '...' if len(article_data['title']) > 50 else article_data['title']
                safe_title = title.encode('utf-8', 'replace').decode('utf-8')
                logger.info(f"Processing article {i}/{len(scraped_articles)}: {safe_title}")
                
                # Generate hash for the URL
                url_hash = hash_url(article_data['url'])
                logger.debug(f"Generated URL hash: {url_hash[:8]}... for URL: {article_data['url']}")
                
                # Check if article already exists using both URL and hashed URL
                if Article.objects.filter(hashed_url=url_hash).exists() or Article.objects.filter(url=article_data['url']).exists():
                    logger.info(f"Article already exists, skipping...")
                    continue
                
                # Create new article
                article = Article.objects.create(
                    title=article_data['title'],
                    url=article_data['url'],
                    hashed_url=url_hash,
                    content=article_data['content'],
                    published_at=article_data['published_at'],
                    source=article_data['source']
                )
                
                new_articles_count += 1
                new_article_ids.append(article.id)
                logger.info(f"Created new article: {article.title[:50]}... (Source: {article.source})")
                
            except Exception as e:
                logger.error(f"Error processing article {article_data.get('url', 'unknown')}: {str(e)}")
                continue
        
        # Second pass: Batch queue all new articles for LLM processing
        if new_article_ids:
            logger.info(f"Batch queuing {len(new_article_ids)} articles for async LLM processing")
            batch_process_articles_task.delay(new_article_ids)
        
        skipped_articles = len(scraped_articles) - new_articles_count
        logger.info(f"Scraping task completed! New articles: {new_articles_count}, Skipped (duplicates): {skipped_articles}, Processing queued: {len(new_article_ids)}")
        logger.info("=== CELERY TASK COMPLETED SUCCESSFULLY ===")
        return {
            'status': 'success',
            'new_articles': new_articles_count,
            'skipped_articles': skipped_articles,
            'processing_queued': len(new_article_ids)
        }
    
    except Exception as e:
        logger.error(f"Scraping task failed: {str(e)}")
        logger.error("=== CELERY TASK FAILED ===")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def batch_process_articles_task(article_ids):
    """Celery task to process multiple articles with LLM in parallel."""
    logger.info(f"Starting batch processing task for {len(article_ids)} articles")
    
    try:
        # Queue individual processing tasks for each article
        # This allows Celery to process them in parallel across multiple workers
        task_ids = []
        for article_id in article_ids:
            task = process_article_task.delay(article_id)
            task_ids.append(task.id)
            logger.info(f"Queued LLM processing for article {article_id} with task ID {task.id}")
        
        logger.info(f"Batch processing task completed. Queued {len(task_ids)} individual processing tasks")
        return {
            'status': 'success',
            'articles_count': len(article_ids),
            'task_ids': task_ids
        }
    
    except Exception as e:
        logger.error(f"Batch processing task failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def process_article_task(article_id):
    """Celery task to process a single article with LLM."""
    logger.info(f"Starting article processing task for article {article_id}")
    
    try:
        article = Article.objects.get(id=article_id)
        llm_service = LLMService()
        
        # Get model from environment variable or use default
        import os
        model = os.getenv('LLM_MODEL', 'gpt-4.1-mini')
        
        try:
            # Generate summary
            logger.info(f"Generating summary for article {article_id} using model: {model}")
            summary = llm_service.generate_summary(article.content, model=model)
            
            if summary:
                article.summary = summary
                logger.info(f"Generated summary for article {article_id}")
            
            # Generate investment suggestion
            logger.info(f"Generating investment suggestion for article {article_id} using model: {model}")
            logger.info("=== DEBUG: About to log article content ===")
            logger.info(f"Article Content Length: {len(article.content) if article.content else 0}")
            logger.info(f"Article Content (first 200 chars): {article.content[:200] if article.content else 'None'}...")
            logger.info("=== DEBUG: About to log summary ===")
            logger.info(f"Summary Length: {len(summary) if summary else 0}")
            logger.info(f"Summary (first 100 chars): {summary[:100] if summary else 'None'}...")
            logger.info("=== DEBUG: Finished logging content and summary ===")
            suggestion_data = llm_service.generate_investment_suggestion(article.content, summary or "", model=model)
            
            if suggestion_data:
                # Handle both old string format and new structured format
                if isinstance(suggestion_data, dict):
                    # New structured format
                    article.suggestion = f"Key Impact: {suggestion_data.get('key_impact', '')}\nInvestment Suggestion: {suggestion_data.get('suggestion', '')}"
                    # Store confidence score if available
                    if 'confidence_score' in suggestion_data and suggestion_data['confidence_score'] is not None:
                        article.confidence_score = suggestion_data['confidence_score']
                        logger.info(f"Set confidence score {article.confidence_score} for article {article_id}")
                else:
                    # Old string format (fallback)
                    article.suggestion = suggestion_data
                logger.info(f"Generated investment suggestion for article {article_id}")
            
            # Save the article
            article.save()
            
            # Send email notification for high confidence scores
            try:
                email_service = EmailNotificationService()
                if email_service.send_high_confidence_alert(article):
                    logger.info(f"High-confidence email alert sent for article {article_id} (confidence: {article.confidence_score})")
                else:
                    logger.debug(f"No email alert sent for article {article_id} (confidence: {article.confidence_score})")
            except Exception as e:
                logger.error(f"Error sending email alert for article {article_id}: {str(e)}")
            
            logger.info(f"Article processing completed for article {article_id}")
            return {
                'status': 'success',
                'article_id': article_id,
                'summary_generated': bool(summary),
                'suggestion_generated': bool(suggestion_data),
                'confidence_score': article.confidence_score,
                'email_sent': email_service.should_send_notification(article.confidence_score) if 'email_service' in locals() else False
            }
        
        finally:
            # Always close the session to free up resources
            llm_service.close_session()
    
    except Article.DoesNotExist:
        logger.error(f"Article {article_id} not found")
        return {
            'status': 'error',
            'error': 'Article not found'
        }
    
    except Exception as e:
        logger.error(f"Article processing task failed for article {article_id}: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def cleanup_old_articles_task():
    """Celery task to clean up old articles (older than 30 days)."""
    logger.info("Starting cleanup task for old articles")
    
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        old_articles = Article.objects.filter(created_at__lt=cutoff_date)
        
        count = old_articles.count()
        old_articles.delete()
        
        logger.info(f"Cleanup task completed. Deleted {count} old articles")
        return {
            'status': 'success',
            'deleted_count': count
        }
    
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


# @shared_task
# def daily_scraping_schedule():
#     """Scheduled task to run daily scraping."""
#     logger.info("Starting daily scraping schedule")
#     
#     try:
#         # Run scraping task
#         scrape_result = scrape_articles_task.delay()
#         
#         # Schedule cleanup task (run less frequently)
#         from datetime import datetime
#         if datetime.now().weekday() == 0:  # Monday
#             cleanup_old_articles_task.delay()
#         
#         logger.info("Daily scraping schedule completed")
#         return {
#             'status': 'success',
#             'scraping_task_id': scrape_result.id
#         }
#     
#     except Exception as e:
#         logger.error(f"Daily scraping schedule failed: {str(e)}")
#         return {
#             'status': 'error',
#             'error': str(e)
#         }

# Note: Daily scraping is now handled by Celery Beat schedule in settings.py
