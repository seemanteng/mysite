import json
import random
from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from .models import Questions, Choice, ThisOrThat, ThisOrThatCategory, Vote
from django.urls import reverse
from django.views import generic
from django.db.models import Avg
from django.contrib.auth.decorators import login_required

class IndexView(generic.ListView):
    template_name = "polls/index.html"
    context_object_name = "latest_question_list"

    def get_queryset(self):
        """Return the last five published questions (not including those set to be published in the furture)."""
        return Questions.objects.filter(pub_date__lte=timezone.now()).order_by("-pub_date")[:5]

class DetailView(generic.DetailView):
    model = Questions
    template_name = "polls/detail.html"
    context_object_name = "question"

    def get_queryset(self):
        """
        Excludes any questions that aren't published yet.
        """
        return Questions.objects.filter(pub_date__lte=timezone.now())


class ResultsView(generic.DetailView):
    model = Questions
    template_name = "polls/results.html"
    context_object_name = "question"

def vote(request, question_id):
    question = get_object_or_404(Questions, pk=question_id)
    try:
        selected_choice = question.choice_set.get(pk=request.POST["choice"])
    except (KeyError, Choice.DoesNotExist):
        return render(request, "polls/detail.html", { "question": question, "error_message": "You didn't select a choice.",})
    else: 
        selected_choice.votes = F("votes") + 1
        selected_choice.save()
        return HttpResponseRedirect(reverse("polls:results", args=(question.id,)))


def this_or_that_home(request):
    """Landing page showing all categories"""
    categories = ThisOrThatCategory.objects.filter(is_active=True)
    
    # Add stats for each category
    for category in categories:
        category.question_count = ThisOrThat.objects.filter(
            category=category, is_active=True
        ).count()
        category.total_votes = Vote.objects.filter(
            this_or_that__category=category
        ).count()
    
    return render(request, 'polls/this_or_that_home.html', {
        'categories': categories
    })

def this_or_that_game(request, category_id):
    """Main game interface"""
    category = get_object_or_404(ThisOrThatCategory, id=category_id, is_active=True)
    
    # Just get all available questions (don't exclude voted ones)
    available_questions = ThisOrThat.objects.filter(
        category=category,
        is_active=True
    )
    
    if not available_questions.exists():
        return render(request, 'polls/category_complete.html', {
            'category': category
        })
    
    question = random.choice(available_questions)
    
    # Calculate progress based on total questions
    total_questions = available_questions.count()
    
    return render(request, 'polls/this_or_that.html', {
        'question': question,
        'category': category,
        'current_question': 1,  # Since they can revote, this is always "current"
        'total_questions': total_questions,
        'progress_percentage': 0  # Or calculate based on some other metric
    })

@require_POST
def vote_this_or_that(request, question_id):
    """Handle voting via AJAX"""
    question = get_object_or_404(ThisOrThat, id=question_id)
    
    try:
        data = json.loads(request.body)
        choice = data.get('choice')
        
        if choice not in ['A', 'B']:
            return JsonResponse({'error': 'Invalid choice'}, status=400)
        
        # Create vote data
        vote_data = {
            'this_or_that': question,
            'choice': choice,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': request.META.get('REMOTE_ADDR'),
        }
        
        if request.user.is_authenticated:
            vote_data['user'] = request.user
            # Check for existing vote by this user
            existing_vote = Vote.objects.filter(
                this_or_that=question,
                user=request.user
            ).first()
        else:
            if not request.session.session_key:
                request.session.create()
            vote_data['session_key'] = request.session.session_key
            # Check for existing vote by this session
            existing_vote = Vote.objects.filter(
                this_or_that=question,
                session_key=request.session.session_key
            ).first()
        
        # Handle existing vote
        if existing_vote:
            # Decrement the old choice count
            if existing_vote.choice == 'A':
                ThisOrThat.objects.filter(id=question_id).update(votes_a=F('votes_a') - 1)
            else:
                ThisOrThat.objects.filter(id=question_id).update(votes_b=F('votes_b') - 1)
            
            # Update the existing vote
            existing_vote.choice = choice
            existing_vote.timestamp = timezone.now()
            existing_vote.user_agent = vote_data['user_agent']
            existing_vote.ip_address = vote_data['ip_address']
            existing_vote.save()
        else:
            # Create new vote
            Vote.objects.create(**vote_data)
        
        # Increment the new choice count
        if choice == 'A':
            ThisOrThat.objects.filter(id=question_id).update(votes_a=F('votes_a') + 1)
        else:
            ThisOrThat.objects.filter(id=question_id).update(votes_b=F('votes_b') + 1)
        
        # Get updated results
        question.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'votes_a': question.votes_a,
            'votes_b': question.votes_b,
            'total_votes': question.total_votes,
            'percentage_a': question.percentage_a,
            'percentage_b': question.percentage_b,
            'winning_option': question.winning_option
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@staff_member_required
def analytics_dashboard(request):
    """Analytics dashboard for admins"""
    # Basic stats
    total_questions = ThisOrThat.objects.filter(is_active=True).count()
    total_votes = Vote.objects.count()
    today_votes = Vote.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # Active users (voted in last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    active_users = Vote.objects.filter(
        timestamp__gte=week_ago,
        user__isnull=False
    ).values('user').distinct().count()
    
    # Categories with stats
    categories = ThisOrThatCategory.objects.filter(is_active=True)
    category_stats = []
    
    for category in categories:
        question_count = ThisOrThat.objects.filter(
            category=category, is_active=True
        ).count()
        category_votes = Vote.objects.filter(
            this_or_that__category=category
        ).count()
        
        category_stats.append({
            'name': category.name,
            'icon': category.icon,
            'question_count': question_count,
            'total_votes': category_votes,
            'avg_votes': round(category_votes / question_count, 1) if question_count > 0 else 0,
            'engagement_rate': round((category_votes / total_votes) * 100, 1) if total_votes > 0 else 0,
            'color': 'ff6b6b',  # You can make this dynamic
            'color_dark': 'ee5a24'
        })
    
    # Trending questions (most votes in last 24 hours)
    yesterday = timezone.now() - timedelta(days=1)
    trending_questions = ThisOrThat.objects.filter(
        is_active=True,
        vote__timestamp__gte=yesterday
    ).annotate(
        recent_votes=Count('vote')
    ).order_by('-recent_votes')[:10]
    
    # Data for charts
    activity_data = get_activity_data(30)  # Last 30 days
    category_data = get_category_data()
    hourly_data = get_hourly_data()
    
    context = {
        'total_questions': total_questions,
        'total_votes': total_votes,
        'today_votes': today_votes,
        'active_users': active_users,
        'categories': categories,
        'category_stats': category_stats,
        'trending_questions': trending_questions,
        'activity_data': json.dumps(activity_data),
        'category_data': json.dumps(category_data),
        'hourly_data': json.dumps(hourly_data),
    }
    
    return render(request, 'polls/analytics_dashboard.html', context)

def get_activity_data(days=30):
    """Get voting activity over time"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Get daily vote counts
    daily_votes = Vote.objects.filter(
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    ).extra(
        select={'day': 'DATE(timestamp)'}
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # Create labels and data arrays
    labels = []
    votes = []
    
    current_date = start_date
    vote_dict = {item['day']: item['count'] for item in daily_votes}
    
    while current_date <= end_date:
        labels.append(current_date.strftime('%b %d'))
        votes.append(vote_dict.get(current_date, 0))
        current_date += timedelta(days=1)
    
    return {'labels': labels, 'votes': votes}

def get_category_data():
    """Get vote distribution by category"""
    category_votes = Vote.objects.values(
        'this_or_that__category__name',
        'this_or_that__category__icon'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    labels = [f"{item['this_or_that__category__icon']} {item['this_or_that__category__name']}" 
              for item in category_votes]
    votes = [item['count'] for item in category_votes]
    
    return {'labels': labels, 'votes': votes}

def get_hourly_data():
    """Get voting patterns by hour of day"""
    # SQLite-compatible way to extract hour
    hourly_votes = Vote.objects.extra(
        select={'hour': "CAST(strftime('%%H', timestamp) AS INTEGER)"}
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Create 24-hour labels
    labels = [f"{i:02d}:00" for i in range(24)]
    votes = [0] * 24
    
    for item in hourly_votes:
        hour = int(item['hour'])
        votes[hour] = item['count']
    
    return {'labels': labels, 'votes': votes}

@staff_member_required
@require_POST
def update_analytics(request):
    """AJAX endpoint to update dashboard data"""
    try:
        data = json.loads(request.body)
        time_period = int(data.get('time_period', 30))
        category_id = data.get('category')
        
        # Filter by category if specified
        vote_filter = Q()
        if category_id and category_id != 'all':
            vote_filter = Q(this_or_that__category_id=category_id)
        
        # Get updated data
        activity_data = get_activity_data(time_period)
        category_data = get_category_data()
        hourly_data = get_hourly_data()
        
        return JsonResponse({
            'activity_data': activity_data,
            'category_data': category_data,
            'hourly_data': hourly_data
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@staff_member_required
def export_analytics(request):
    """Export analytics data as CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="thisorthat_analytics.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Question', 'Category', 'Option A', 'Option B', 'Votes A', 'Votes B', 'Total Votes', 'Created'])
    
    questions = ThisOrThat.objects.select_related('category').all()
    for q in questions:
        writer.writerow([
            f"{q.option_a} vs {q.option_b}",
            q.category.name,
            q.option_a,
            q.option_b,
            q.votes_a,
            q.votes_b,
            q.total_votes,
            q.created_at.strftime('%Y-%m-%d')
        ])
    
    return response

def this_or_that_game(request, category_id):
    """Main game interface with proper progress tracking"""
    category = get_object_or_404(ThisOrThatCategory, id=category_id, is_active=True)
    
    # Check if user wants to reset/play again
    reset = request.GET.get('reset')
    
    if reset:
        # Clear user's previous votes for this category
        if request.user.is_authenticated:
            Vote.objects.filter(
                user=request.user,
                this_or_that__category=category
            ).delete()
        elif request.session.session_key:
            Vote.objects.filter(
                session_key=request.session.session_key,
                this_or_that__category=category
            ).delete()
        
        # Redirect to start fresh (without reset parameter)
        return redirect('polls:this_or_that', category_id=category_id)
    
    # Get all questions for this category
    all_questions = ThisOrThat.objects.filter(category=category, is_active=True)
    
    if not all_questions.exists():
        return render(request, 'polls/category_complete.html', {
            'category': category
        })
    
    # Get questions user has voted on
    voted_questions = []
    if request.user.is_authenticated:
        voted_questions = Vote.objects.filter(
            user=request.user,
            this_or_that__category=category
        ).values_list('this_or_that_id', flat=True)
    elif request.session.session_key:
        voted_questions = Vote.objects.filter(
            session_key=request.session.session_key,
            this_or_that__category=category
        ).values_list('this_or_that_id', flat=True)
    
    # Get remaining questions
    remaining_questions = all_questions.exclude(id__in=voted_questions)
    
    # If no remaining questions, redirect to summary
    if not remaining_questions.exists():
        return redirect('polls:quiz_summary', category_id=category_id)
    
    # Get next question (random from remaining)
    question = random.choice(remaining_questions)
    
    # Calculate progress
    total_questions = all_questions.count()
    answered_questions = len(voted_questions)
    progress_percentage = (answered_questions / total_questions) * 100 if total_questions > 0 else 0
    
    # Check if there are more questions after this one
    has_next_question = remaining_questions.count() > 1
    
    return render(request, 'polls/this_or_that.html', {
        'question': question,
        'category': category,
        'current_question': answered_questions + 1,
        'total_questions': total_questions,
        'progress_percentage': progress_percentage,
        'has_next_question': has_next_question
    })

# Add new quiz summary view
def quiz_summary(request, category_id):
    """Display quiz completion summary with all results"""
    category = get_object_or_404(ThisOrThatCategory, id=category_id, is_active=True)
    
    # Get all questions in this category with their current vote counts
    questions = ThisOrThat.objects.filter(category=category, is_active=True)
    
    # Get user's votes for this category
    user_votes = {}
    if request.user.is_authenticated:
        votes = Vote.objects.filter(
            user=request.user,
            this_or_that__category=category
        ).select_related('this_or_that')
        user_votes = {vote.this_or_that.id: vote.choice for vote in votes}
    elif request.session.session_key:
        votes = Vote.objects.filter(
            session_key=request.session.session_key,
            this_or_that__category=category
        ).select_related('this_or_that')
        user_votes = {vote.this_or_that.id: vote.choice for vote in votes}
    
    # Prepare questions with calculated percentages and user choices
    questions_with_results = []
    total_votes = 0
    
    for question in questions:
        total_votes += question.total_votes
        questions_with_results.append({
            'option_a': question.option_a,
            'option_b': question.option_b,
            'votes_a': question.votes_a,
            'votes_b': question.votes_b,
            'total_votes': question.total_votes,
            'percentage_a': question.percentage_a,
            'percentage_b': question.percentage_b,
            'user_choice': user_votes.get(question.id, None),  # Add user's choice
        })
    
    # Calculate summary stats
    total_questions = questions.count()
    avg_votes_per_question = (total_votes / total_questions) if total_questions > 0 else 0
    
    return render(request, 'polls/quiz_summary.html', {
        'category': category,
        'questions_with_results': questions_with_results,
        'total_questions': total_questions,
        'total_votes': total_votes,
        'avg_votes_per_question': avg_votes_per_question,
    })
# Update your vote_this_or_that view (keeping the revote logic you wanted)
@require_POST
def vote_this_or_that(request, question_id):
    """Handle voting via AJAX with revote capability"""
    question = get_object_or_404(ThisOrThat, id=question_id)
    
    try:
        data = json.loads(request.body)
        choice = data.get('choice')
        
        if choice not in ['A', 'B']:
            return JsonResponse({'error': 'Invalid choice'}, status=400)
        
        # Create vote data
        vote_data = {
            'this_or_that': question,
            'choice': choice,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': request.META.get('REMOTE_ADDR'),
        }
        
        if request.user.is_authenticated:
            vote_data['user'] = request.user
            # Check for existing vote by this user
            existing_vote = Vote.objects.filter(
                this_or_that=question,
                user=request.user
            ).first()
        else:
            if not request.session.session_key:
                request.session.create()
            vote_data['session_key'] = request.session.session_key
            # Check for existing vote by this session
            existing_vote = Vote.objects.filter(
                this_or_that=question,
                session_key=request.session.session_key
            ).first()
        
        # Handle existing vote (revote logic)
        if existing_vote:
            # Decrement the old choice count
            if existing_vote.choice == 'A':
                ThisOrThat.objects.filter(id=question_id).update(votes_a=F('votes_a') - 1)
            else:
                ThisOrThat.objects.filter(id=question_id).update(votes_b=F('votes_b') - 1)
            
            # Update the existing vote
            existing_vote.choice = choice
            existing_vote.timestamp = timezone.now()
            existing_vote.user_agent = vote_data['user_agent']
            existing_vote.ip_address = vote_data['ip_address']
            existing_vote.save()
        else:
            # Create new vote
            Vote.objects.create(**vote_data)
        
        # Increment the new choice count
        if choice == 'A':
            ThisOrThat.objects.filter(id=question_id).update(votes_a=F('votes_a') + 1)
        else:
            ThisOrThat.objects.filter(id=question_id).update(votes_b=F('votes_b') + 1)
        
        # Get updated results
        question.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'votes_a': question.votes_a,
            'votes_b': question.votes_b,
            'total_votes': question.total_votes,
            'percentage_a': question.percentage_a,
            'percentage_b': question.percentage_b,
            'winning_option': question.winning_option
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Restrict analytics to admin only
@staff_member_required
def analytics_dashboard(request):
    """Analytics dashboard for admins only"""
    # Your existing analytics code here...
    pass