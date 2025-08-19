import datetime
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

# Create your models here.
class Questions(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField("date published")
    def __str__(self):
        return self.question_text
    def was_published_recently(self):
        now = timezone.now()
        return now - datetime.timedelta(days=1) <= self.pub_date <= now

class Choice(models.Model):
    question = models.ForeignKey(Questions, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default = 0)
    def __str__(self):
        return self.choice_text
    
class ThisOrThatCategory(models.Model):
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=20, default="🎯")  # Emoji icon
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.icon} {self.name}"
    
    class Meta:
        verbose_name_plural = "Categories"

class ThisOrThat(models.Model):
    # The main "This or That" question
    category = models.ForeignKey(ThisOrThatCategory, on_delete=models.CASCADE)
    option_a = models.CharField(max_length=100)
    option_b = models.CharField(max_length=100)
    option_a_image = models.URLField(blank=True)  # Optional image URLs
    option_b_image = models.URLField(blank=True)
    
    # Voting counts
    votes_a = models.IntegerField(default=0)
    votes_b = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.option_a} vs {self.option_b}"
    
    @property
    def total_votes(self):
        return self.votes_a + self.votes_b
    
    @property
    def percentage_a(self):
        if self.total_votes == 0:
            return 50
        return round((self.votes_a / self.total_votes) * 100, 1)
    
    @property
    def percentage_b(self):
        if self.total_votes == 0:
            return 50
        return round((self.votes_b / self.total_votes) * 100, 1)
    
    @property
    def winning_option(self):
        if self.votes_a > self.votes_b:
            return 'A'
        elif self.votes_b > self.votes_a:
            return 'B'
        return 'TIE'

class Vote(models.Model):
    # Track individual votes for analytics
    CHOICE_OPTIONS = [
        ('A', 'Option A'),
        ('B', 'Option B'),
    ]
    
    this_or_that = models.ForeignKey(ThisOrThat, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)  # For anonymous users
    choice = models.CharField(max_length=1, choices=CHOICE_OPTIONS)
    
    # Analytics data
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True)  # Browser info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        # Prevent duplicate votes from same user/session
        pass 
    
    def __str__(self):
        identifier = self.user.username if self.user else f"Session {self.session_key[:8]}"
        return f"{identifier} voted {self.choice} on {self.this_or_that}"