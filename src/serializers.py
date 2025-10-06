from rest_framework import serializers
from .models import Article


class ArticleSerializer(serializers.ModelSerializer):
    """Serializer for Article model."""
    
    is_processed = serializers.ReadOnlyField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'url', 'hashed_url', 'content', 'published_at', 
            'summary', 'suggestion', 'confidence_score', 'source', 'created_at', 
            'updated_at', 'is_processed'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ArticleListSerializer(serializers.ModelSerializer):
    """Simplified serializer for article list view."""
    
    is_processed = serializers.ReadOnlyField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'published_at', 'summary', 
            'suggestion', 'confidence_score', 'source', 'is_processed'
        ]
