from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Questions, Choice, ThisOrThat, ThisOrThatCategory, Vote

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 3

class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {"fields": ["question_text"]}),
        ("Date information", {"fields": ["pub_date"], "classes": ["collapse"]}),
    ]
    inlines = [ChoiceInline]
    list_display = ["question_text", "pub_date", "was_published_recently"]
    list_filter = ["pub_date"]


admin.site.register(Questions)
admin.site.register(Choice)

@admin.register(ThisOrThatCategory)
class ThisOrThatCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'question_count', 'total_votes', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    
    def question_count(self, obj):
        count = obj.thisorthat_set.filter(is_active=True).count()
        return format_html(
            '<a href="{}?category__id__exact={}">{} questions</a>',
            reverse('admin:polls_thisorthat_changelist'),
            obj.id,
            count
        )
    question_count.short_description = "Questions"
    
    def total_votes(self, obj):
        votes = Vote.objects.filter(this_or_that__category=obj).count()
        return f"{votes:,} votes"
    total_votes.short_description = "Total Votes"

@admin.register(ThisOrThat)
class ThisOrThatAdmin(admin.ModelAdmin):
    list_display = [
        'question_preview', 'category', 'votes_display', 'winning_side', 
        'total_votes', 'is_active', 'featured', 'created_at'
    ]
    list_filter = ['category', 'is_active', 'featured', 'created_at']
    search_fields = ['option_a', 'option_b']
    readonly_fields = ['votes_a', 'votes_b', 'created_at', 'vote_breakdown']
    
    fieldsets = [
        ('Question Details', {
            'fields': ['category', 'option_a', 'option_b']
        }),
        ('Images (Optional)', {
            'fields': ['option_a_image', 'option_b_image'],
            'classes': ['collapse']
        }),
        ('Status', {
            'fields': ['is_active', 'featured']
        }),
        ('Vote Statistics', {
            'fields': ['votes_a', 'votes_b', 'vote_breakdown'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['created_at'],
            'classes': ['collapse']
        })
    ]
    
    def question_preview(self, obj):
        return f"{obj.option_a} vs {obj.option_b}"
    question_preview.short_description = "Question"
    
    def votes_display(self, obj):
        return format_html(
            '<div style="display: flex; gap: 10px;">'
            '<span style="color: #dc3545; font-weight: bold;">A: {}</span>'
            '<span style="color: #007bff; font-weight: bold;">B: {}</span>'
            '</div>',
            obj.votes_a, obj.votes_b
        )
    votes_display.short_description = "Votes (A | B)"
    
    def winning_side(self, obj):
        try:
            # Get vote counts directly from the model fields (not properties)
            votes_a = obj.votes_a
            votes_b = obj.votes_b
            total_votes = votes_a + votes_b
            
            if total_votes == 0:
                return format_html('<span style="color: #6c757d;">No votes yet</span>')
            
            if votes_a > votes_b:
                percentage = (votes_a / total_votes) * 100
                return format_html('<span style="color: #dc3545; font-weight: bold;">A ({:.1f}%)</span>', percentage)
            elif votes_b > votes_a:
                percentage = (votes_b / total_votes) * 100
                return format_html('<span style="color: #007bff; font-weight: bold;">B ({:.1f}%)</span>', percentage)
            else:
                return format_html('<span style="color: #6c757d;">Tie</span>')
        except Exception as e:
            # More detailed error message for debugging
            return format_html('<span style="color: #dc3545;" title="Error: {} | votes_a: {} | votes_b: {}">Debug: {}</span>', 
                             str(e), getattr(obj, 'votes_a', 'N/A'), getattr(obj, 'votes_b', 'N/A'), type(e).__name__)
    winning_side.short_description = "Winner"
    
    def vote_breakdown(self, obj):
        try:
            # Get vote counts directly from the model fields
            votes_a = obj.votes_a
            votes_b = obj.votes_b
            total_votes = votes_a + votes_b
            
            if total_votes == 0:
                return "No votes yet"
            
            # Calculate percentages directly from vote counts
            percentage_a = (votes_a / total_votes) * 100
            percentage_b = (votes_b / total_votes) * 100
            
            return format_html(
                '<div style="margin: 10px 0;">'
                '<div style="margin-bottom: 10px;">'
                '<strong>{}</strong>: {} votes ({:.1f}%)<br>'
                '<div style="background: #dc3545; height: 10px; width: {}%; margin: 5px 0;"></div>'
                '</div>'
                '<div>'
                '<strong>{}</strong>: {} votes ({:.1f}%)<br>'
                '<div style="background: #007bff; height: 10px; width: {}%; margin: 5px 0;"></div>'
                '</div>'
                '<p style="margin-top: 10px; color: #6c757d;">Total: {} votes</p>'
                '</div>',
                obj.option_a, votes_a, percentage_a, percentage_a,
                obj.option_b, votes_b, percentage_b, percentage_b,
                total_votes
            )
        except Exception as e:
            return format_html('<span style="color: #dc3545;" title="Error: {}">Error in breakdown: {}</span>', str(e), type(e).__name__)
    vote_breakdown.short_description = "Vote Breakdown"

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['voter_info', 'question_preview', 'choice_display', 'timestamp']
    list_filter = ['choice', 'timestamp', 'this_or_that__category']
    search_fields = ['user__username', 'this_or_that__option_a', 'this_or_that__option_b']
    readonly_fields = ['user', 'session_key', 'this_or_that', 'choice', 'timestamp', 'user_agent', 'ip_address']
    
    def voter_info(self, obj):
        if obj.user:
            return format_html(
                '<strong>{}</strong><br><small>Registered User</small>',
                obj.user.username
            )
        else:
            return format_html(
                '<small>Anonymous</small><br><small>Session: {}</small>',
                obj.session_key[:8] if obj.session_key else 'Unknown'
            )
    voter_info.short_description = "Voter"
    
    def question_preview(self, obj):
        return f"{obj.this_or_that.option_a} vs {obj.this_or_that.option_b}"
    question_preview.short_description = "Question"
    
    def choice_display(self, obj):
        option = obj.this_or_that.option_a if obj.choice == 'A' else obj.this_or_that.option_b
        color = '#dc3545' if obj.choice == 'A' else '#007bff'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}: {}</span>',
            color, obj.choice, option
        )
    choice_display.short_description = "Choice"
    
    def has_add_permission(self, request):
        # Prevent manual vote creation
        return False

# Customize admin site
admin.site.site_header = "This or That Admin"
admin.site.site_title = "This or That"
admin.site.index_title = "Welcome to This or That Administration"