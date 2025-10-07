import logging
from django.conf import settings
from django.template.loader import render_to_string
from typing import Optional, List
from .models import Article
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

logger = logging.getLogger('news')


class EmailNotificationService:
    """Service for sending email notifications for high-confidence investment suggestions."""
    
    def __init__(self):
        self.enabled = getattr(settings, 'EMAIL_NOTIFICATION_ENABLED', True)
        self.recipients = getattr(settings, 'EMAIL_RECIPIENTS', [])
        self.confidence_threshold = getattr(settings, 'CONFIDENCE_THRESHOLD', 0.7)
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        self.sendgrid_api_key = getattr(settings, 'SENDGRID_API_KEY', '')
        self.sg_client = SendGridAPIClient(self.sendgrid_api_key) if self.sendgrid_api_key else None

        logger.info(f"Email Service Initialized - Enabled: {self.enabled}, Recipients: {len(self.recipients) if self.recipients else 0}, From: {self.from_email or 'NOT SET'}, SendGrid API Key: {'SET' if self.sendgrid_api_key else 'NOT SET'}, Threshold: {self.confidence_threshold}")
    
    def should_send_notification(self, confidence_score: Optional[float]) -> bool:
        """Check if notification should be sent based on confidence score."""
        if not self.enabled:
            logger.info(f"Email notification skipped: EMAIL_NOTIFICATION_ENABLED is False")
            return False
        
        if not self.recipients or not self.from_email:
            logger.warning(f"Email notifications disabled: Recipients={self.recipients}, From={self.from_email or 'NOT SET'}")
            return False
        
        if confidence_score is None:
            logger.info(f"Email notification skipped: confidence_score is None")
            return False
        
        if confidence_score >= self.confidence_threshold:
            logger.info(f"Email notification WILL be sent: confidence_score ({confidence_score}) >= threshold ({self.confidence_threshold})")
            return True
        else:
            logger.info(f"Email notification skipped: confidence_score ({confidence_score}) < threshold ({self.confidence_threshold})")
            return False
    
    def send_high_confidence_alert(self, article: Article) -> bool:
        """Send email notification for high-confidence investment suggestion."""
        if not self.should_send_notification(article.confidence_score):
            return False
        
        try:
            subject = f"🚨 High-Confidence Investment Alert: {article.title[:50]}..."
            
            # Create email content
            context = {
                'article': article,
                'confidence_score': article.confidence_score,
                'confidence_percentage': round(article.confidence_score * 100, 1),
                'threshold': self.confidence_threshold,
            }
            
            # Plain text version
            message = self._create_plain_text_message(context)
            
            # HTML version
            html_message = self._create_html_message(context)
            
            # Send email using SendGrid
            if not self.sg_client:
                logger.error('SendGrid client not initialized - missing API key')
                return False
            
            try:
                # Create SendGrid mail object
                from_email = Email(self.from_email)
                to_emails = [To(email) for email in self.recipients]
                plain_text_content = Content('text/plain', message)
                html_content = Content('text/html', html_message)
                
                mail = Mail(
                    from_email=from_email,
                    to_emails=to_emails,
                    subject=subject,
                    plain_text_content=plain_text_content,
                    html_content=html_content
                )
                
                # Send the email
                response = self.sg_client.send(mail)
                result = response.status_code in [200, 201, 202]
            except Exception as sendgrid_error:
                logger.error(f'SendGrid API error: {str(sendgrid_error)}')
                return False
            
            if result:
                logger.info(f"High-confidence alert sent for article {article.id} (confidence: {article.confidence_score})")
                return True
            else:
                logger.error(f"Failed to send high-confidence alert for article {article.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending high-confidence alert for article {article.id}: {str(e)}")
            return False
    
    def _create_plain_text_message(self, context: dict) -> str:
        """Create plain text email message."""
        article = context['article']
        confidence_percentage = context['confidence_percentage']
        
        message = f"""
🚨 HIGH-CONFIDENCE INVESTMENT ALERT 🚨

Confidence Score: {confidence_percentage}% (Threshold: {self.confidence_threshold * 100}%)

Article: {article.title}
Source: {article.source}
Published: {article.published_at.strftime('%Y-%m-%d %H:%M UTC')}
URL: {article.url}

SUMMARY:
{article.summary or 'No summary available'}

INVESTMENT SUGGESTION:
{article.suggestion or 'No suggestion available'}

---
This alert was generated by Investment Wizard
Confidence threshold: {self.confidence_threshold * 100}%
        """.strip()
        
        return message
    
    def _create_html_message(self, context: dict) -> str:
        """Create HTML email message."""
        article = context['article']
        confidence_percentage = context['confidence_percentage']
        
        # Color coding based on confidence level
        if confidence_percentage >= 90:
            confidence_color = "#d32f2f"  # Red for very high confidence
            confidence_emoji = "🔥"
        elif confidence_percentage >= 80:
            confidence_color = "#f57c00"  # Orange for high confidence
            confidence_emoji = "⚠️"
        else:
            confidence_color = "#1976d2"  # Blue for medium-high confidence
            confidence_emoji = "📈"
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>High-Confidence Investment Alert</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: {confidence_color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .confidence {{ font-size: 24px; font-weight: bold; color: {confidence_color}; }}
                .article-title {{ font-size: 18px; font-weight: bold; margin: 15px 0; }}
                .summary, .suggestion {{ background-color: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid {confidence_color}; }}
                .footer {{ background-color: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .url {{ word-break: break-all; color: #1976d2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{confidence_emoji} HIGH-CONFIDENCE INVESTMENT ALERT {confidence_emoji}</h1>
                <div class="confidence">Confidence Score: {confidence_percentage}%</div>
                <p>Threshold: {self.confidence_threshold * 100}%</p>
            </div>
            
            <div class="content">
                <div class="article-title">{article.title}</div>
                <p><strong>Source:</strong> {article.source}</p>
                <p><strong>Published:</strong> {article.published_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                <p><strong>URL:</strong> <a href="{article.url}" class="url">{article.url}</a></p>
                
                <div class="summary">
                    <h3>📋 SUMMARY</h3>
                    <p>{article.summary or 'No summary available'}</p>
                </div>
                
                <div class="suggestion">
                    <h3>💡 INVESTMENT SUGGESTION</h3>
                    <p>{article.suggestion or 'No suggestion available'}</p>
                </div>
            </div>
            
            <div class="footer">
                <p>This alert was generated by Investment Wizard</p>
                <p>Confidence threshold: {self.confidence_threshold * 100}%</p>
            </div>
        </body>
        </html>
        """
        
        return html_message
    
    def test_email_configuration(self) -> bool:
        """Test email configuration by sending a test email."""
        if not self.enabled or not self.recipients or not self.from_email:
            logger.error("Email configuration incomplete")
            return False
        
        try:
            if not self.sg_client:
                logger.error('SendGrid client not initialized - missing API key')
                return False
            
            # Create test email using SendGrid
            from_email = Email(self.from_email)
            to_emails = [To(email) for email in self.recipients]
            plain_text_content = Content('text/plain', 'This is a test email to verify your email configuration is working correctly.')
            
            mail = Mail(
                from_email=from_email,
                to_emails=to_emails,
                subject='Investment Wizard - Email Configuration Test',
                plain_text_content=plain_text_content
            )
            
            # Send the test email
            response = self.sg_client.send(mail)
            result = response.status_code in [200, 201, 202]
            logger.info("Test email sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send test email: {str(e)}")
            return False
    
    def get_configuration_status(self) -> dict:
        """Get current email configuration status."""
        return {
            'enabled': self.enabled,
            'recipients_count': len(self.recipients) if self.recipients else 0,
            'from_email': self.from_email,
            'confidence_threshold': self.confidence_threshold,
            'configuration_complete': bool(self.enabled and self.recipients and self.from_email)
        }


if __name__ == "__main__":
    # Test email service
    import os
    import sys
    import django
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_wizard.settings')
    django.setup()
    
    email_service = EmailNotificationService()
    print("Email Configuration Status:")
    print(email_service.get_configuration_status())
    
    if email_service.get_configuration_status()['configuration_complete']:
        print("\nTesting email configuration...")
        if email_service.test_email_configuration():
            print("✅ Email configuration test successful!")
        else:
            print("❌ Email configuration test failed!")
    else:
        print("❌ Email configuration incomplete!")

