from django import forms
from django.contrib.auth.models import User, Group
from .models import Child, SubscriptionType, Subscription, TrainingSession

class ParentCreateForm(forms.Form):
    username = forms.CharField(label='Логин')
    email = forms.EmailField(label='Email')
    password = forms.CharField(label='Временный пароль', widget=forms.PasswordInput)

class StudentForm(forms.ModelForm):
    # добавляем выбор «Ребёнок» или «Взрослый»
    student_type = forms.ChoiceField(
        choices=(('child','Ребёнок'), ('adult','Взрослый')),
        widget=forms.RadioSelect, label='Тип ученика'
    )
    account_username = forms.CharField(
        required=False, label='Логин',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Логин'})
    )
    account_email    = forms.EmailField(
        required=False, label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'})
    )
    account_password = forms.CharField(
        required=False, label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль', 'autocomplete': 'new-password'})
    )
    
    class Meta:
        model = Child
        fields = ['student_type', 'parent', 'first_name', 'last_name', 'birth_date', 'gender', 'notes']
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фамилия'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'gender': forms.RadioSelect(attrs={'class': 'btn-check'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Примечания'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = User.objects.filter(groups__name='Parent').order_by('username')
        if self.instance and self.instance.pk:
            self.fields['student_type'].initial = 'adult' if self.instance.is_adult else 'child'
            if self.instance.is_adult and self.instance.account_user:
                self.fields['account_username'].initial = self.instance.account_user.username
                self.fields['account_email'].initial = self.instance.account_user.email

    def clean(self):
        cleaned = super().clean()
        stype = cleaned.get('student_type')
        if stype == 'child':
            if not cleaned.get('parent'):
                self.add_error('parent', 'Для ребёнка выберите родителя.')
        elif stype == 'adult':
            uname = cleaned.get('account_username') or ''
            pwd   = cleaned.get('account_password') or ''
            if not uname:
                self.add_error('account_username', 'Укажите логин взрослого.')
            # требовать пароль только при создании нового account_user
            if not self.instance.pk or not self.instance.account_user:
                if not pwd:
                    self.add_error('account_password', 'Укажите пароль.')
            # уникальность логина
            if uname:
                qs = User.objects.filter(username=uname)
                if self.instance.account_user:
                    qs = qs.exclude(pk=self.instance.account_user.pk)
                if qs.exists():
                    self.add_error('account_username', 'Такой логин уже существует.')
        return cleaned


    # добавление абонемента при сохранении ученика
    def save(self, commit=True):
        obj = super().save(commit=False)
        stype = self.cleaned_data['student_type']
        obj.is_adult = (stype == 'adult')

        # логика взрослого аккаунта
        if obj.is_adult:
            uname = self.cleaned_data.get('account_username')
            email = self.cleaned_data.get('account_email')
            pwd   = self.cleaned_data.get('account_password')

            if obj.account_user:
                u = obj.account_user
                if email is not None:
                    u.email = email
                if pwd:
                    u.set_password(pwd)
                u.is_staff = False
                u.save()
            else:
                u = User.objects.create_user(username=uname, email=email or '', password=pwd)
                group, _ = Group.objects.get_or_create(name='Student')
                u.groups.add(group)
                u.is_staff = False
                u.save()
                obj.account_user = u
            obj.parent = None
        else:
            obj.account_user = None  # взрослый аккаунт не нужен

        if commit:
            obj.save()

        # ► ГАРАНТИЯ АБОНЕМЕНТА (создадим, если отсутствует)
        sub_type = SubscriptionType.objects.first()
        if sub_type:
            Subscription.objects.get_or_create(
                child=obj,
                defaults={
                    'sub_type': sub_type,
                    'lessons_remaining': sub_type.lessons_count,
                    'price': sub_type.price,
                    'paid': False
                }
            )
        return obj



class SubscriptionTypeForm(forms.ModelForm):
    class Meta:
        model = SubscriptionType
        fields = ['name', 'lessons_count', 'price']
        labels = {
            'name': 'Название',
            'lessons_count': 'Количество занятий',
            'price': 'Цена',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Например: Базовый'
            }),
            'lessons_count': forms.NumberInput(attrs={
                'class': 'form-control stepper-input',
                'min': 1, 'max': 64, 'step': 1, 'inputmode': 'numeric'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'step': '0.01', 'inputmode': 'decimal'
            }),
        }

class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ['child', 'sub_type', 'lessons_remaining', 'price', 'paid']

class TrainingSessionForm(forms.ModelForm):
    class Meta:
        model = TrainingSession
        fields = ['start', 'duration_minutes', 'participants', 'notes']
        widgets = {
            'start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class AddVisitForm(forms.Form):
    child_id = forms.IntegerField(widget=forms.HiddenInput)

class IssueSubscriptionForm(forms.Form):
    sub_type = forms.ModelChoiceField(
        queryset=SubscriptionType.objects.all(),
        label='Тип абонемента',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    price = forms.DecimalField(label='Цена', max_digits=10, decimal_places=2, required=False)
    mark_paid = forms.BooleanField(label='Сразу отметить как оплачен', required=False)
