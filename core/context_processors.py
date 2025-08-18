def user_roles(request):
    user = request.user
    is_admin   = user.is_authenticated and (user.is_staff or user.groups.filter(name='Admin').exists())
    is_parent  = user.is_authenticated and user.groups.filter(name='Parent').exists() and not is_admin
    is_student = user.is_authenticated and user.groups.filter(name='Student').exists() and not (is_admin or is_parent)
    return {'IS_ADMIN': is_admin, 'IS_PARENT': is_parent, 'IS_STUDENT': is_student} 