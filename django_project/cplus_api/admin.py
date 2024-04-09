from django.contrib import admin, messages
from core.celery import cancel_task
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import InputLayer, OutputLayer
from cplus_api.models.profile import UserProfile


def cancel_scenario_task(modeladmin, request, queryset):
    for scenario_task in queryset:
        if scenario_task.task_id:
            cancel_task(scenario_task.task_id)
    modeladmin.message_user(
        request,
        'Tasks have been cancelled',
        messages.INFO
    )


class ScenarioTaskAdmin(admin.ModelAdmin):
    list_display = ('scenario_name', 'submitted_by', 'task_id', 'status',
                    'progress', 'started_at', 'finished_at',
                    'last_update', 'uuid')
    search_fields = ['status', 'task_id', 'uuid']
    actions = [cancel_scenario_task]
    list_filter = ["status", "submitted_by"]
    list_per_page = 30

    def scenario_name(self, obj: ScenarioTask):
        if not obj.detail or 'scenario_name' not in obj.detail:
            return '-'
        return obj.detail['scenario_name']


class InputLayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'owner', 'created_on', 'layer_type',
                    'size', 'component_type', 'privacy_type')
    search_fields = ['name', 'uuid']
    list_filter = ["layer_type", "owner", "component_type", "privacy_type"]


class OutputLayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'owner', 'created_on', 'layer_type',
                    'size', 'scenario', 'group', 'is_final_output')
    search_fields = ['name', 'uuid']
    list_filter = ["layer_type", "owner", "is_final_output"]


admin.site.register(ScenarioTask, ScenarioTaskAdmin)
admin.site.register(InputLayer, InputLayerAdmin)
admin.site.register(OutputLayer, OutputLayerAdmin)
admin.site.register(UserProfile)
