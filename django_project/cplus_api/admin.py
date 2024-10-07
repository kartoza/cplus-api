from django.contrib import admin, messages
from core.celery import cancel_task
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import InputLayer, OutputLayer, MultipartUpload
from cplus_api.models.profile import UserProfile, UserRoleType
from cplus_api.tasks.verify_input_layer import verify_input_layer


def cancel_scenario_task(modeladmin, request, queryset):
    """Cancel scenario task action."""
    for scenario_task in queryset:
        if scenario_task.task_id:
            cancel_task(scenario_task.task_id)
    modeladmin.message_user(
        request,
        'Tasks have been cancelled',
        messages.INFO
    )


def trigger_verify_input_layer(modeladmin, request, queryset):
    """Trigger verify input layer in the background."""
    for input_layer in queryset:
        verify_input_layer.delay(input_layer.id)
    modeladmin.message_user(
        request,
        'Tasks will be run in the background!',
        messages.INFO
    )


class ScenarioTaskAdmin(admin.ModelAdmin):
    list_display = ('scenario_name', 'uuid', 'submitted_by', 'task_id',
                    'status', 'progress', 'started_at', 'finished_at',
                    'last_update')
    search_fields = ['status', 'task_id', 'uuid']
    actions = [cancel_scenario_task]
    list_filter = ["status", "submitted_by"]
    list_per_page = 30

    def scenario_name(self, obj: ScenarioTask):
        if not obj.detail or 'scenario_name' not in obj.detail:
            return '-'
        return obj.detail['scenario_name']


class InputLayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'uuid', 'owner', 'created_on', 'layer_type',
                    'size', 'component_type', 'privacy_type')
    search_fields = ['name', 'uuid']
    list_filter = ["layer_type", "owner", "component_type", "privacy_type"]
    readonly_fields = ['layer_type', 'component_type', 'uuid', 'modified_on']
    actions = [trigger_verify_input_layer]


class OutputLayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'owner', 'created_on', 'layer_type',
                    'size', 'scenario', 'group', 'is_final_output')
    search_fields = ['name', 'uuid']
    list_filter = ["layer_type", "owner", "is_final_output"]


class UserRoleTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'user', 'role')

    def name(self, obj: UserProfile):
        return f'{obj.user.first_name} {obj.user.last_name}'

    def email(self, obj: UserProfile):
        return obj.user.email


admin.site.register(ScenarioTask, ScenarioTaskAdmin)
admin.site.register(InputLayer, InputLayerAdmin)
admin.site.register(OutputLayer, OutputLayerAdmin)
admin.site.register(UserRoleType, UserRoleTypeAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(MultipartUpload)
