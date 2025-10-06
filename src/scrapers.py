import requests
from bs4 import BeautifulSoup
from newspaper import Article as NewsArticle
from datetime import datetime, timedelta
import logging
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger('news')


class BaseScraper:
    """Base class for news scrapers."""
    
    def __init__(self, source: str, base_url: str):
        self.source = source
        self.base_url = base_url
        self.session = requests.Session()
        self._setup_headers()
    
    def _setup_headers(self):
        """Setup headers based on the source."""
        if self.source.lower() == 'reuters':
            # Enhanced headers for Reuters (anti-bot detection)
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            })
    
    def establish_session(self):
        """Visit the main page to establish cookies and session."""
        try:
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            logger.info(f"Established session with {self.source}")
        except Exception as e:
            logger.warning(f"Failed to establish session with {self.source}: {str(e)}")
    
    def get_article_links(self) -> List[str]:
        """Get list of article URLs from the source."""
        raise NotImplementedError
    
    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape individual article content."""
        try:
            if self.source.lower() == 'reuters':
                # Reuters needs custom session handling due to anti-bot protection
                headers = {
                    'Referer': self.base_url,
                    'Sec-Fetch-Site': 'same-origin'
                }
                
                # Download content using our session with proper headers
                response = self.session.get(url, timeout=10, headers=headers)
                response.raise_for_status()
                
                # Use newspaper3k for content extraction with downloaded HTML
                article = NewsArticle(url)
                article.set_html(response.text)
                article.parse()
            else:
                # TechCrunch and other sources work fine with newspaper3k's default downloader
                article = NewsArticle(url)
                article.download()
                article.parse()
            
            if not article.title or not article.text:
                logger.warning(f"Failed to extract content from {url}")
                return None
            
            # Get article publish date
            publish_date = article.publish_date or datetime.now()
            current_time = datetime.now()
            
            # Ensure both datetimes are timezone-naive for comparison
            if publish_date.tzinfo is not None:
                publish_date = publish_date.replace(tzinfo=None)
            if current_time.tzinfo is not None:
                current_time = current_time.replace(tzinfo=None)
            
            # Check if article is within last 24 hours
            if publish_date < current_time - timedelta(hours=24):
                logger.info(f"Article too old (>{publish_date}), skipping: {url}")
                return None
            
            return {
                'title': article.title.strip(),
                'url': url,
                'content': article.text.strip(),
                'published_at': publish_date,
                'source': self.source
            }
        
        except Exception as e:
            logger.error(f"Error scraping article {url}: {str(e)}")
            return None
    
    def scrape_all(self) -> List[Dict]:
        """Scrape all articles from the source."""
        articles = []
        links = self.get_article_links()
        
        logger.info(f"Found {len(links)} articles from {self.source}")
        
        for i, link in enumerate(links):
            try:
                article_data = self.scrape_article(link)
                
                if article_data:
                    # Safely encode title for logging
                    title = article_data['title'][:50] + '...' if len(article_data['title']) > 50 else article_data['title']
                    # Use safe encoding for logging
                    safe_title = title.encode('utf-8', 'replace').decode('utf-8')
                    logger.info(f"Scraped {i+1}/{len(links)} article: {safe_title}")
                    articles.append(article_data)
                else:
                    # If article_data is None, it means the article was too old
                    # Since articles are in chronological order, stop here
                    logger.info(f"Stopping scraping at article {i+1} - article too old (24h limit reached)")
                    break
                
                # Rate limiting
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"Error processing article {link}: {str(e)}")
                continue
        
        logger.info(f"Successfully scraped {len(articles)} articles from {self.source}")
        return articles


class TechCrunchScraper(BaseScraper):
    """Scraper for TechCrunch latest news."""
    
    def __init__(self):
        super().__init__('TechCrunch', 'https://techcrunch.com')
        self.tech_url = 'https://techcrunch.com/latest/'
    

    def get_article_links(self) -> List[str]:
        """Get TechCrunch article links (Latest News)."""
        try:
            # TechCrunch doesn't need session establishment
            response = self.session.get(self.tech_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            links = []
            # Select all article <a> tags inside wp-block-post list
            for a in soup.select("ul.wp-block-post-template li.wp-block-post a.loop-card__title-link"):
                href = a.get("href")
                if href and href.startswith("https://techcrunch.com/"):
                    if not any(x in href for x in ["/video/", "/events/", "/podcast/", "/newsletters/", "/author/"]):
                        if href not in links:
                            links.append(href)

            return links

        except Exception as e:
            logger.error(f"Error getting TechCrunch article links: {str(e)}")
            return []



class ReutersMarketScraper(BaseScraper):
    """Scraper for Reuters Markets sections (e.g., US, Stocks)."""
    
    def __init__(self, section: str):
        """
        section: 'us' or 'stocks'
        """
        super().__init__('Reuters', 'https://www.reuters.com')
        self.section = section
        self.url = f"https://www.reuters.com/markets/{section}/"
    
    def get_article_links(self) -> List[str]:
        """Get Reuters article links from the section page."""
        try:
            self.establish_session()
            response = self.session.get(self.url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # Select <a> tags with data-testid="Heading"
            for a in soup.find_all("a", attrs={"data-testid": "Heading"}, href=True):
                href = a["href"]
                # Full URL
                full_url = urljoin(self.base_url, href)
                if full_url not in links:
                    links.append(full_url)
            
            return links
        except Exception as e:
            logger.error(f"Error getting Reuters {self.section} links: {str(e)}")
            return []


class ScrapingService:
    """Main scraping service that coordinates all scrapers."""
    
    def __init__(self):
        self.scrapers = [
            TechCrunchScraper(),
            # ReutersMarketScraper('us'),      # Disabled
            # ReutersMarketScraper('stocks'),  # Disabled
        ]
    
    def scrape_all_sources(self) -> List[Dict]:
        """Scrape all configured sources."""
        all_articles = []
        
        logger.info(f"Starting scraping from {len(self.scrapers)} source(s): {[s.source for s in self.scrapers]}")
        
        for i, scraper in enumerate(self.scrapers, 1):
            try:
                logger.info(f"[{i}/{len(self.scrapers)}] Starting scraping from {scraper.source}")
                articles = scraper.scrape_all()
                all_articles.extend(articles)
                logger.info(f"[{i}/{len(self.scrapers)}] Completed scraping from {scraper.source}: {len(articles)} articles")
            
            except Exception as e:
                logger.error(f"[{i}/{len(self.scrapers)}] Error scraping from {scraper.source}: {str(e)}")
                continue
        
        logger.info(f"Total articles scraped from TechCrunch: {len(all_articles)}")
        return all_articles


if __name__ == "__main__":
    # Setup logging to see INFO messages
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # # Test Reuters scraper properly
    # reuters_scraper = ReutersTechScraper()
    # scrape_content = reuters_scraper.scrape_article(
    #     "https://www.reuters.com/business/finance/trumps-h-1b-visa-crackdown-upends-indian-it-industrys-playbook-2025-09-21/"
    #     )
    # print(scrape_content)

    # # Test TechCrunch scraper properly
    # techcrunch_scraper = TechCrunchScraper()
    # scrape_content = techcrunch_scraper.scrape_article(
    #     "https://techcrunch.com/2025/09/21/techcrunch-mobility-the-two-robotaxi-battlegrounds-that-matter/"
    # )
    # print(scrape_content)

    # Test scraping all article link for only techcrunch scraper
    # techcrunch_scraper = TechCrunchScraper()
    # all_articles = techcrunch_scraper.scrape_all()
    # print(f"Total articles scraped: {len(all_articles)}")
    # for article in all_articles:
    #     print(f"Title: {article['title']}")
    #     print(f"URL: {article['url']}")
    #     print("---")

    # Test scraping all article link for only techcrunch scraper
    techcrunch_scraper = TechCrunchScraper()
    all_articles = techcrunch_scraper.scrape_all()