from django.db import models
from django.utils import timezone


class Article(models.Model):
    """Model representing a news article."""
    
    SOURCE_CHOICES = [
        ('TechCrunch', 'TechCrunch'),
        ('Reuters', 'Reuters'),  # Keep for existing data
    ]
    
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    url = models.URLField(max_length=500, unique=True)
    hashed_url = models.CharField(max_length=64, unique=True, help_text="SHA-256 hash of the URL for duplicate detection")
    content = models.TextField()
    published_at = models.DateTimeField()
    summary = models.TextField(null=True, blank=True)
    suggestion = models.TextField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True, help_text="Confidence score between 0 and 1 for market impact prediction")
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['source']),
            models.Index(fields=['published_at']),
            models.Index(fields=['url']),
            models.Index(fields=['hashed_url']),
        ]
    
    def __str__(self):
        return f"{self.source}: {self.title[:50]}..."
    
    @property
    def is_processed(self):
        """Check if article has been processed (has summary and suggestion)."""
        return bool(self.summary and self.suggestion)
