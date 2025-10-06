from django.core.management.base import BaseCommand
from news.llm_service import LLMService


class Command(BaseCommand):
    help = 'Manage LLM cache operations'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['clear', 'stats', 'setup'],
            help='Cache action to perform'
        )

    def handle(self, *args, **options):
        action = options['action']
        llm_service = LLMService()

        if action == 'clear':
            self.stdout.write('Clearing LLM cache...')
            llm_service.clear_cache()
            self.stdout.write(
                self.style.SUCCESS('✅ LLM cache cleared successfully!')
            )

        elif action == 'stats':
            self.stdout.write('Getting cache statistics...')
            stats = llm_service.get_cache_stats()
            self.stdout.write(f"Cache Backend: {stats.get('backend', 'Unknown')}")
            self.stdout.write(f"Timeout: {stats.get('timeout', 'Unknown')} seconds")
            self.stdout.write(f"Status: {stats.get('status', 'Unknown')}")

        elif action == 'setup':
            self.stdout.write('Setting up cache table...')
            from django.core.management import execute_from_command_line
            try:
                execute_from_command_line(['manage.py', 'createcachetable'])
                self.stdout.write(
                    self.style.SUCCESS('✅ Cache table created successfully!')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error creating cache table: {e}')
                )
