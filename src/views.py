from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Article
from .serializers import ArticleSerializer, ArticleListSerializer
from .tasks import scrape_articles_task
from .email_service import EmailNotificationService


class ArticleListView(generics.ListAPIView):
    """List all articles with pagination."""
    
    queryset = Article.objects.all()
    serializer_class = ArticleListSerializer


class ArticleDetailView(generics.RetrieveAPIView):
    """Retrieve a single article by ID."""
    
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer


@api_view(['POST'])
def trigger_scraping(request):
    """Manually trigger the scraping job."""
    import logging
    logger = logging.getLogger('news')
    
    try:
        logger.info("Scraping job requested via API")
        
        # Start the scraping task asynchronously
        task = scrape_articles_task.delay()
        
        logger.info(f"Scraping task queued with ID: {task.id}")
        
        return Response({
            'message': 'Scraping job started successfully',
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
    
    except Exception as e:
        logger.error(f"Failed to start scraping job: {str(e)}")
        return Response({
            'error': f'Failed to start scraping job: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_result(request):
    """Get all articles with title, url, summary, and suggestion."""
    try:
        articles = Article.objects.all()
        
        result = []
        for article in articles:
            result.append({
                'title': article.title,
                'url': article.url,
                'summary': article.summary,
                'suggestion': article.suggestion,
                'confidence_score': article.confidence_score
            })
        
        return Response({
            'data': result,
            'count': len(result)
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'error': f'Failed to retrieve articles: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def health_check(request):
    """Health check endpoint."""
    return Response({
        'status': 'healthy',
        'message': 'Investment Wizard API is running'
    })


@api_view(['POST'])
def test_email_config(request):
    """Test email configuration by sending a test email."""
    try:
        email_service = EmailNotificationService()
        
        # Get configuration status
        config_status = email_service.get_configuration_status()
        
        if not config_status['configuration_complete']:
            return Response({
                'status': 'error',
                'message': 'Email configuration incomplete',
                'config_status': config_status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Send test email
        if email_service.test_email_configuration():
            return Response({
                'status': 'success',
                'message': 'Test email sent successfully',
                'config_status': config_status
            })
        else:
            return Response({
                'status': 'error',
                'message': 'Failed to send test email',
                'config_status': config_status
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Error testing email configuration: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def email_config_status(request):
    """Get email configuration status."""
    try:
        email_service = EmailNotificationService()
        config_status = email_service.get_configuration_status()
        
        return Response({
            'status': 'success',
            'config_status': config_status
        })
    
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Error getting email configuration: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
