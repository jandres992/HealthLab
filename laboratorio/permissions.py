"""Permisos de negocio por rol para el módulo laboratorio.

TRANSITORIO: esta clase se reemplaza por `usuarios.permissions.PermisoPorAccion`
con la matriz de acciones en el paso "validación y cierre" de la Fase 1.
Mientras tanto usa el módulo común de roles (usuarios/roles.py).
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from usuarios.roles import roles_de as _roles_usuario


class LaboratorioRolPermission(BasePermission):
    """Controla acceso por rol de negocio (Médico, Técnico, Bacteriólogo, Auditor, Admin)."""

    def has_permission(self, request, view):
        if request.method in ("OPTIONS", "HEAD"):
            return True

        action = getattr(view, "action", "")
        view_name = view.__class__.__name__

        # Middleware sin JWT para ingestar tramas seriales.
        if view_name == "LecturaEquipoSerialViewSet" and action == "create":
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        roles = _roles_usuario(request.user)
        if "administrador" in roles:
            return True

        readonly = request.method in SAFE_METHODS

        if view_name in {
            "CatalogoCupsViewSet",
            "ConfiguracionEquipoViewSet",
            "TipoDocumentoPacienteViewSet",
            "SexoBiologicoViewSet",
            "EstadoOrdenViewSet",
            "EstadoExamenViewSet",
            "EstadoMuestraViewSet",
        }:
            return readonly and bool(roles.intersection({"bacteriologo", "auditor"}))

        if view_name == "ParametroExamenViewSet":
            if readonly:
                return bool(roles.intersection({"bacteriologo", "auditor"}))
            return "bacteriologo" in roles

        if view_name == "PacienteViewSet":
            if readonly:
                return bool(roles.intersection({"medico", "tecnico_de_enfermeria", "bacteriologo", "auditor"}))
            return bool(roles.intersection({"medico", "tecnico_de_enfermeria"}))

        if view_name == "OrdenLaboratorioViewSet":
            if action == "export_rips":
                return "auditor" in roles
            if action == "admitir":
                return bool(roles.intersection({"tecnico_de_enfermeria", "medico"}))
            if readonly:
                return bool(roles.intersection({"medico", "tecnico_de_enfermeria", "bacteriologo", "auditor"}))
            return "medico" in roles

        if view_name == "MuestraFisicaViewSet":
            if action in {"recibir_laboratorio", "rechazar"}:
                return "bacteriologo" in roles
            if action == "buscar":
                return bool(roles.intersection({"tecnico_de_enfermeria", "bacteriologo", "medico"}))
            if readonly:
                return bool(roles.intersection({"tecnico_de_enfermeria", "bacteriologo", "medico", "auditor"}))
            return "tecnico_de_enfermeria" in roles

        if view_name == "ExamenSolicitadoViewSet":
            if action in {"aprobar", "rechazar"}:
                return "bacteriologo" in roles
            if readonly:
                return bool(roles.intersection({"medico", "bacteriologo", "auditor"}))
            return bool(roles.intersection({"medico", "bacteriologo"}))

        if view_name == "LecturaEquipoSerialViewSet":
            if action == "procesar":
                return "bacteriologo" in roles
            return readonly and bool(roles.intersection({"bacteriologo", "auditor"}))

        if view_name in {"ResultadoAnalitoViewSet", "InformeResultadosViewSet"}:
            return readonly and bool(roles.intersection({"medico", "bacteriologo", "auditor"}))

        if view_name == "NotificacionViewSet":
            return bool(roles.intersection({"medico", "tecnico_de_enfermeria", "bacteriologo", "auditor"}))

        return False
