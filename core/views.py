from datetime import timedelta, date
from calendar import monthrange

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import PasswordChangeView
from django.db.models import Prefetch, Count
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy

from .forms import (
    AddVisitForm, StudentForm, ParentCreateForm,
    SubscriptionForm, SubscriptionTypeForm, TrainingSessionForm, IssueSubscriptionForm,
    BootstrapPasswordChangeForm,
)

from .models import Child, Subscription, SubscriptionType, TrainingSession
from collections import defaultdict, OrderedDict

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


class CustomPasswordChangeView(PasswordChangeView):
    form_class = BootstrapPasswordChangeForm
    template_name = 'password_change.html'
    success_url = reverse_lazy('home')

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
    
    slots_by_day = _group_timeslots(sessions)

    form = TrainingSessionForm()
    context = {
        'days': days,
        'sessions': sessions,
        'form': form,
        'start': start,
        'prev_start': start - timedelta(days=7),
        'next_start': start + timedelta(days=7),
        'slots_by_day': slots_by_day,
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
    slots_by_day = _group_timeslots(sessions)

    # Соседние месяцы
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Разбиение на недели для календаря
    weeks = []
    week = []
    for day in days:
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []

    # Добавить последнюю неполную неделю
    if week:
        weeks.append(week)

    return render(request, 'admin/sessions_month.html', {
        'days': days,
        'month': month,
        'year': year,
        'sessions': sessions,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'slots_by_day': slots_by_day,
        'weeks': weeks,  # Передаем недели для календаря
    })

@login_required
@user_passes_test(is_admin)
def session_create(request):
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST)
        if form.is_valid():
            session = form.save()
            if form.cleaned_data.get('fill_month'):
                start = session.start
                duration = session.duration_minutes
                notes = session.notes
                participants = session.participants.all()
                next_start = start + timedelta(days=7)
                while next_start.month == start.month:
                    new_session = TrainingSession.objects.create(
                        start=next_start,
                        duration_minutes=duration,
                        notes=notes,
                    )
                    new_session.participants.set(participants)
                    next_start += timedelta(days=7)
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
def session_edit(request, pk):
    session = get_object_or_404(TrainingSession, pk=pk)
    week_start = session.start.date() - timedelta(days=session.start.weekday())

    if request.method == 'POST':
        form = TrainingSessionForm(request.POST, instance=session)
        form.fields.pop('fill_month', None)
        if form.is_valid():
            form.save()
            messages.success(request, 'Занятие обновлено')
            return redirect(f"{reverse('sessions_week')}?start={week_start:%Y-%m-%d}")
    else:
        form = TrainingSessionForm(instance=session)
        form.fields.pop('fill_month', None)

    return render(request, 'admin/session_edit.html', {
        'form': form,
        'session': session,
        'week_start': week_start,
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def session_delete(request, pk):
    session = get_object_or_404(TrainingSession, pk=pk)
    start_date = session.start.date()
    session.delete()
    week_start = start_date - timedelta(days=start_date.weekday())
    messages.success(request, 'Занятие удалено')
    return redirect(f"{reverse('sessions_week')}?start={week_start:%Y-%m-%d}")

@login_required
@user_passes_test(is_admin)
def children_list(request):
    children = Child.objects.select_related('parent', 'account_user').order_by('first_name', 'last_name')
    subs_qs = Subscription.objects.filter(child__in=children).select_related('sub_type', 'child')
    subs = {s.child_id: s for s in subs_qs}

    return render(request, 'admin/children_list.html', {
        'children': children,
        'subs': subs,
        'add_visit_form': AddVisitForm(),
    })

@login_required
@user_passes_test(is_admin)
def child_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ученик создан')
            return redirect('children_list')
        return render(request, 'admin/child_create.html', {'form': form})
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
            user = form.save()
            messages.success(request, 'Родитель успешно создан!')
            return redirect('parent_create')
        else:
            messages.error(request, f'Ошибка при создании родителя: {form.errors}')
    else:
        form = ParentCreateForm()

    # Получаем список всех родителей
    try:
        parent_group = Group.objects.get(name='Parent')
        parents = User.objects.filter(groups=parent_group).order_by('username')
    except Group.DoesNotExist:
        parents = User.objects.none()

    return render(request, 'admin/parent_create.html', {
        'form': form,
        'parents': parents,  # Передаем актуальный список родителей в контекст
    })
    # if request.method == 'POST':
    #     form = ParentCreateForm(request.POST)
    #     if form.is_valid():
    #         first_name = form.cleaned_data['first_name']
    #         last_name = form.cleaned_data['last_name']
    #         username = form.cleaned_data['username']
    #         email = form.cleaned_data['email']
    #         password = form.cleaned_data['password']
    #         if User.objects.filter(username=username).exists():
    #             messages.error(request, 'Логин уже существует')
    #         else:
    #             user = User.objects.create_user(username=username, email=email, password=password)
    #             user.first_name = first_name
    #             user.last_name = last_name
    #             group, _ = Group.objects.get_or_create(name='Parent')
    #             user.groups.add(group)
    #             user.is_staff = False
    #             user.save()
    #             messages.success(request, 'Родитель создан')
    #             return redirect('parent_create')
    # else:
    #     form = ParentCreateForm()

    # Список родителей (только из группы Parent) + дети
    # try:
    #     parent_group = Group.objects.get(name='Parent')
    #     parents = (User.objects.filter(groups=parent_group)
    #                .prefetch_related(Prefetch('children', queryset=Child.objects.order_by('first_name')))
    #                .annotate(children_count=Count('children'))
    #                .order_by('username'))
    # except Group.DoesNotExist:
    #     parents = User.objects.none()

    # return render(request, 'admin/parent_create.html', {
    #     'form': form,
    #     'parents': parents,
    # })

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
def my_schedule(request):
    # Админа отправим в дашборд
    if is_admin(request.user):
        return redirect('admin_dashboard')

    if is_parent(request.user):
        children_ids = list(request.user.children.values_list('id', flat=True))
        sessions = (TrainingSession.objects
                    .filter(participants__in=children_ids)
                    .distinct().order_by('start'))
        return render(request, 'parent/my_schedule.html', {'sessions': sessions})
    # студент-взрослый
    student = getattr(request.user, 'student_profile', None)
    if not student:
        return HttpResponseForbidden('Нет доступа.')
    sessions = TrainingSession.objects.filter(participants=student).distinct().order_by('start')
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


@login_required
@user_passes_test(is_admin)
def issue_subscription(request, pk):
    child = get_object_or_404(Child, pk=pk)
    types_ = SubscriptionType.objects.all()
    if request.method == 'POST':
        form = IssueSubscriptionForm(request.POST)
        if form.is_valid():
            sub_type = form.cleaned_data['sub_type']
            price = form.cleaned_data['price'] or sub_type.price
            mark_paid = form.cleaned_data['mark_paid']

            # создаём или обновляем
            sub, _created = Subscription.objects.update_or_create(
                child=child,
                defaults={
                    'sub_type': sub_type,
                    'lessons_remaining': sub_type.lessons_count if mark_paid else 0,
                    'price': price,
                    'paid': bool(mark_paid),
                }
            )
            if mark_paid and sub.lessons_remaining == 0:
                sub.lessons_remaining = sub.sub_type.lessons_count
                sub.save()

            messages.success(request, 'Абонемент выдан/обновлён')
            return redirect('children_list')
    else:
        form = IssueSubscriptionForm()
    return render(request, 'admin/issue_subscription.html', {'form': form, 'child': child, 'types': types_})


@login_required
@user_passes_test(is_admin)
def subscription_edit(request, pk):
    """Изменение типа абонемента для существующего ученика."""
    child = get_object_or_404(Child, pk=pk, subscription__isnull=False)
    sub = child.subscription
    types_ = SubscriptionType.objects.all()

    if request.method == 'POST':
        form = IssueSubscriptionForm(request.POST)
        if form.is_valid():
            sub.sub_type = form.cleaned_data['sub_type']
            sub.price = form.cleaned_data['price'] or sub.sub_type.price
            if form.cleaned_data['mark_paid']:
                sub.paid = True
                sub.lessons_remaining = sub.sub_type.lessons_count
            else:
                if sub.lessons_remaining > sub.sub_type.lessons_count:
                    sub.lessons_remaining = sub.sub_type.lessons_count
            sub.save()
            messages.success(request, 'Абонемент обновлён')
            return redirect('children_list')
    else:
        form = IssueSubscriptionForm(initial={
            'sub_type': sub.sub_type,
            'price': sub.price or sub.sub_type.price,
        })
    return render(request, 'admin/subscription_edit.html', {'form': form, 'child': child, 'sub': sub, 'types': types_})

@login_required
@user_passes_test(is_admin)
@require_POST
def child_delete(request, pk):
    child = get_object_or_404(Child, pk=pk)
    # по ТЗ удаляем только ученика; его аккаунт-взрослого (если был) оставляем
    name = str(child)
    child.delete()  # Subscription удалится каскадом, M2M из занятий — тоже
    messages.success(request, f'Ученик «{name}» удалён.')
    return redirect('children_list')


@login_required
@user_passes_test(is_admin)
@require_POST
def parent_delete(request, user_id):
    # удаляем только пользователей из группы Parent
    parent = get_object_or_404(User, pk=user_id, groups__name='Parent')
    username = parent.username
    # FK Child.parent(on_delete=CASCADE) — все дети удалятся автоматически
    parent.delete()
    messages.success(request, f'Родитель «{username}» и его дети удалены.')
    return redirect('parent_create')

def _group_timeslots(sessions_qs):
    """
    На вход: queryset TrainingSession с prefetch_related('participants') и order_by('start').
    На выход: dict {date: [ {start, end, participants(list), session_ids(list)}... ]}
    Группирует карточки по (start, end), объединяя участников.
    """
    slots_by_day = defaultdict(lambda: OrderedDict())
    for s in sessions_qs:
        day = s.start.date()
        key = (s.start, s.end)
        if key not in slots_by_day[day]:
            slots_by_day[day][key] = {
                'start': s.start,
                'end': s.end,
                'participants': {},
                'session_ids': [s.id],
            }
        else:
            slots_by_day[day][key]['session_ids'].append(s.id)

        # набираем участников без дублей
        for p in s.participants.all():
            slots_by_day[day][key]['participants'][p.id] = p

    # превращаем dict участников в список
    out = {}
    for day, od in slots_by_day.items():
        items = []
        for slot in od.values():
            slot['participants'] = list(slot['participants'].values())
            items.append(slot)
        out[day] = items
    return out