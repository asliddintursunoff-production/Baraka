from django.apps import AppConfig


class TelemetryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.telemetry"
    label = "telemetry"

    def ready(self) -> None:
        from django.db.backends.signals import connection_created

        from .timing import db_execute_wrapper

        def _install(sender: object, connection: object, **kwargs: object) -> None:
            wrappers = getattr(connection, "execute_wrappers", None)
            if wrappers is not None and db_execute_wrapper not in wrappers:
                wrappers.append(db_execute_wrapper)

        connection_created.connect(_install, weak=False, dispatch_uid="telemetry_db_timing")
