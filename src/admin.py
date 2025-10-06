from django.contrib import admin
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'source', 'published_at', 'is_processed', 'created_at']
    list_filter = ['source', 'published_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-published_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'url', 'source', 'published_at')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('AI Processing', {
            'fields': ('summary', 'suggestion')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
