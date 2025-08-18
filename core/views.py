from datetime import timedelta, date
from calendar import monthrange

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.db.models import Prefetch, Count
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AddVisitForm, StudentForm, ParentCreateForm,
    SubscriptionForm, SubscriptionTypeForm, TrainingSessionForm
)

from .models import Child, Subscription, SubscriptionType, TrainingSession

# --- роли ---

def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.groups.filter(name='Admin').exists())

def is_parent(user):
    return user.is_authenticated and user.groups.filter(name='Parent').exists() and not is_admin(user)

# --- корневая ---

@login_required
def home(request):
    if is_admin(request.user):
        return redirect('admin_dashboard')
    return redirect('my_schedule')

# --- админ ---

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    return render(request, 'admin/dashboard.html')

@login_required
@user_passes_test(is_admin)
def sessions_week(request):
    today = timezone.localdate()
    start_str = request.GET.get('start')
    if start_str:
        try:
            start = date.fromisoformat(start_str)
        except (ValueError, TypeError):
            start = today - timedelta(days=today.weekday())
    else:
        start = today - timedelta(days=today.weekday())

    days = [start + timedelta(days=i) for i in range(7)]
    end = days[-1] + timedelta(days=1)

    sessions = (TrainingSession.objects
                .filter(start__date__gte=days[0], start__date__lt=end)
                .prefetch_related('participants'))

    form = TrainingSessionForm()
    context = {
        'days': days,
        'sessions': sessions,
        'form': form,
        'start': start,
        'prev_start': start - timedelta(days=7),
        'next_start': start + timedelta(days=7),
    }
    return render(request, 'admin/sessions_week.html', context)

@login_required
@user_passes_test(is_admin)
def sessions_month(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    # Нормализуем значения месяца на случай 0/13
    while month < 1:
        year -= 1
        month += 12
    while month > 12:
        year += 1
        month -= 12

    first_day = date(year, month, 1)
    _, days_in_month = monthrange(year, month)
    days = [first_day + timedelta(days=i) for i in range(days_in_month)]

    sessions = (TrainingSession.objects
                .filter(start__year=year, start__month=month)
                .prefetch_related('participants'))

    # Соседние месяцы
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return render(request, 'admin/sessions_month.html', {
        'days': days,
        'month': month,
        'year': year,
        'sessions': sessions,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
    })

@login_required
@user_passes_test(is_admin)
def session_create(request):
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Занятие создано')
            return redirect('sessions_week')
    else:
        form = TrainingSessionForm()
    return render(request, 'admin/sessions_week.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def session_add_child(request, pk, child_id):
    session = get_object_or_404(TrainingSession, pk=pk)
    child = get_object_or_404(Child, pk=child_id)
    session.participants.add(child)
    messages.success(request, f'Добавлен {child} в занятие.')
    return redirect('sessions_week')

@login_required
@user_passes_test(is_admin)
def children_list(request):
    children = Child.objects.select_related('parent').prefetch_related('subscription')
    # Для быстрого доступа к абонементам
    subs = {s.child_id: s for s in Subscription.objects.select_related('sub_type', 'child')}
    return render(request, 'admin/children_list.html', {'children': children, 'subs': subs, 'add_visit_form': AddVisitForm()})

@login_required
@user_passes_test(is_admin)
def child_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ученик создан')
            return redirect('children_list')
    else:
        form = StudentForm()
    return render(request, 'admin/child_create.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def subscriptions_list(request):
    subs = Subscription.objects.select_related('child', 'child__parent', 'sub_type').all()
    return render(request, 'admin/subscriptions_list.html', {'subs': subs})

@login_required
@user_passes_test(is_admin)
def subscription_types(request):
    if request.method == 'POST':
        form = SubscriptionTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тип абонемента сохранен')
            return redirect('subscription_types')
    else:
        form = SubscriptionTypeForm()
    types_ = SubscriptionType.objects.all()
    return render(request, 'admin/subscription_types.html', {'form': form, 'types': types_})

@login_required
@user_passes_test(is_admin)
def parent_create(request):
    if request.method == 'POST':
        form = ParentCreateForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Логин уже существует')
            else:
                user = User.objects.create_user(username=username, email=email, password=password)
                group, _ = Group.objects.get_or_create(name='Parent')
                user.groups.add(group)
                user.is_staff = False
                user.save()
                messages.success(request, 'Родитель создан')
                return redirect('parent_create')
    else:
        form = ParentCreateForm()

    # Список родителей (только из группы Parent) + дети
    try:
        parent_group = Group.objects.get(name='Parent')
        parents = (User.objects.filter(groups=parent_group)
                   .prefetch_related(Prefetch('children', queryset=Child.objects.order_by('first_name')))
                   .annotate(children_count=Count('children'))
                   .order_by('username'))
    except Group.DoesNotExist:
        parents = User.objects.none()

    return render(request, 'admin/parent_create.html', {
        'form': form,
        'parents': parents,
    })

@login_required
@user_passes_test(is_admin)
def add_visit(request):
    if request.method == 'POST':
        form = AddVisitForm(request.POST)
        if form.is_valid():
            child_id = form.cleaned_data['child_id']
            child = get_object_or_404(Child, pk=child_id)
            sub = getattr(child, 'subscription', None)
            if sub and sub.add_visit():
                messages.success(request, f'Зачтено посещение для {child}. Остаток: {sub.lessons_remaining}.')
            else:
                messages.error(request, 'Нельзя зачесть посещение: нет активного оплаченного абонемента или нулевой остаток.')
    return redirect('children_list')

@login_required
@user_passes_test(is_admin)
def mark_payment(request):
    if request.method == 'POST':
        child_id = int(request.POST.get('child_id'))
        child = get_object_or_404(Child, pk=child_id)
        sub = getattr(child, 'subscription', None)
        if sub:
            sub.mark_paid_and_reset()
            messages.success(request, f'Оплата отмечена для {child}. Остаток установлен: {sub.lessons_remaining}.')
        else:
            messages.error(request, 'Абонемент не найден')
    return redirect('children_list')

# --- родитель ---

@login_required
@user_passes_test(is_parent)
def my_schedule(request):
    # Админа отправим в дашборд
    if is_admin(request.user):
        return redirect('admin_dashboard')

    sessions = TrainingSession.objects.none()

    if is_parent(request.user):
        children_ids = list(request.user.children.values_list('id', flat=True))
        sessions = (TrainingSession.objects
                    .filter(participants__in=children_ids)
                    .distinct().order_by('start'))
    else:
        # студент-взрослый
        student = getattr(request.user, 'student_profile', None)
        if student:
            sessions = (TrainingSession.objects
                        .filter(participants=student)
                        .distinct().order_by('start'))
        else:
            return HttpResponseForbidden('Нет доступа.')

    return render(request, 'parent/my_schedule.html', {'sessions': sessions})

@login_required
@user_passes_test(is_parent)
def my_children(request):
    children = request.user.children.select_related().all()
    subs = {s.child_id: s for s in Subscription.objects.filter(child__in=children).select_related('sub_type')}
    return render(request, 'parent/my_children.html', {'children': children, 'subs': subs})

@login_required
@user_passes_test(is_admin)
def child_detail(request, pk):
    child = get_object_or_404(
        Child.objects.select_related('parent').prefetch_related('sessions', 'subscription__sub_type'),
        pk=pk
    )
    sub = getattr(child, 'subscription', None)
    sessions = (child.sessions.all().order_by('-start'))  # последние сверху
    return render(request, 'admin/child_detail.html', {
        'child': child,
        'sub': sub,
        'sessions': sessions,
    })

@login_required
@user_passes_test(is_admin)
def child_edit(request, pk):
    child = get_object_or_404(Child, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=child)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные ученика обновлены')
            return redirect('children_list')
    else:
        form = StudentForm(instance=child)
    return render(request, 'admin/child_edit.html', {'form': form, 'child': child})
