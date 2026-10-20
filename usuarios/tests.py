"""
Pruebas del bloque de seguridad de usuarios (§15.5, RF-01.1, RF-05, RF-05.1,
RF-05.2, RF-05.3, RN-16, RN-20, RNF-25, RNF-26).
"""
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Auditoria, DispositivoConfianza, Permiso, TipoUsuario, UsuarioXPermiso
from .testing import CONTRASENA_PRUEBA, crear_usuario


class BaseUsuariosTest(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia los contadores de throttling entre pruebas
        self.admin = crear_usuario('admin1', 'administrador')
        self.medico = crear_usuario('medico1', 'medico', p_nombre='Ana', p_apellido='López')
        self.bacteriologo = crear_usuario('bact1', 'bacteriologo')
        self.auditor = crear_usuario('auditor1', 'auditor')
        self.sin_rol = crear_usuario('sinrol')

    def login(self, username, password=CONTRASENA_PRUEBA, **extra):
        return self.client.post('/usr/login/', {'username': username, 'password': password, **extra}, format='json')


class AutenticacionTests(BaseUsuariosTest):
    def test_login_devuelve_roles_y_acciones(self):
        r = self.login('medico1')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('access', r.data)
        self.assertEqual(r.data['roles'], ['medico'])
        self.assertEqual(r.data['rol'], 'Médico')
        self.assertIn('ordenes.crear', r.data['acciones'])
        self.assertNotIn('examenes.aprobar', r.data['acciones'])
        self.assertNotIn('is_superuser', r.data['user'])
        self.assertTrue(Auditoria.objects.filter(accion='login.exito', usuario=self.medico).exists())

    def test_login_sin_rol_es_403(self):
        r = self.login('sinrol')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(r.data['estado'], 'no_autorizado')
        self.assertTrue(Auditoria.objects.filter(accion='login.sin_rol', exito=False).exists())

    def test_login_fallido_mensaje_generico_y_auditado(self):
        r = self.login('medico1', password='incorrecta')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(r.data['mensaje'], 'Usuario o contraseña incorrectos.')
        r2 = self.login('noexiste', password='incorrecta')
        self.assertEqual(r2.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(r2.data['mensaje'], r.data['mensaje'])
        self.assertEqual(Auditoria.objects.filter(accion='login.fallo').count(), 2)

    def test_login_registra_dispositivo(self):
        r = self.login('medico1', device_id='abc-123', nombre_dispositivo='Pixel 7')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(DispositivoConfianza.objects.filter(usuario=self.medico, device_id='abc-123').exists())

    def test_login_limita_intentos(self):
        for _ in range(5):
            self.login('medico1', password='mala')
        r = self.login('medico1', password='mala')
        self.assertEqual(r.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(r.data['estado'], 'limite_excedido')

    def test_refresh_y_logout(self):
        tokens = self.login('medico1').data
        r = self.client.post('/usr/token/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        r2 = self.client.post('/usr/logout/', {'refresh': r.data['refresh']}, format='json')
        self.assertEqual(r2.status_code, 200)
        r3 = self.client.post('/usr/token/refresh/', {'refresh': r.data['refresh']}, format='json')
        self.assertEqual(r3.status_code, 401)


class AccesoSinAutenticacionTests(BaseUsuariosTest):
    def test_endpoints_de_usuarios_exigen_token(self):
        for ruta in ('/usr/usuarios/', '/usr/usuarios-permisos/', '/usr/dispositivos-confianza/',
                     '/usr/me/', '/usr/departamentos/', '/api/v1/pacientes/'):
            r = self.client.get(ruta)
            self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED, ruta)
            self.assertEqual(r.data['estado'], 'no_autenticado', ruta)

    def test_login_y_refresh_son_publicos(self):
        self.assertNotEqual(self.login('medico1').status_code, 401)
        r = self.client.post('/usr/token/refresh/', {'refresh': 'x'}, format='json')
        self.assertIn(r.status_code, (400, 401))


class GestionDeCuentasTests(BaseUsuariosTest):
    def test_medico_no_gestiona_usuarios(self):
        self.client.force_authenticate(self.medico)
        self.assertEqual(self.client.get('/usr/usuarios/').status_code, 403)
        r = self.client.post('/usr/usuarios/', {'username': 'x', 'password': CONTRASENA_PRUEBA}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_auditor_solo_lee_usuarios(self):
        self.client.force_authenticate(self.auditor)
        self.assertEqual(self.client.get('/usr/usuarios/').status_code, 200)
        r = self.client.post('/usr/usuarios/', {'username': 'x', 'password': CONTRASENA_PRUEBA}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_admin_crea_usuario_sin_devolver_password(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/usr/usuarios/', {
            'username': 'nuevo', 'password': CONTRASENA_PRUEBA, 'email': 'n@x.co',
            'registro_profesional': 'RM-12345',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn('password', r.data)
        self.assertEqual(r.data['roles'], [])
        self.assertTrue(Auditoria.objects.filter(accion='usuario.crear', entidad_id=str(r.data['id'])).exists())

    def test_password_debil_rechazada(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/usr/usuarios/', {'username': 'nuevo2', 'password': '1234'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.data['errores'])

    def test_desactivar_es_logico_y_revoca_tokens(self):
        tokens = self.login('medico1').data
        self.client.force_authenticate(self.admin)
        r = self.client.delete(f'/usr/usuarios/{self.medico.pk}/')
        self.assertEqual(r.status_code, 200)
        self.medico.refresh_from_db()
        self.assertFalse(self.medico.is_active)
        self.client.force_authenticate(None)
        r2 = self.client.post('/usr/token/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(r2.status_code, 401)

    def test_admin_no_se_desactiva_a_si_mismo(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f'/usr/usuarios/{self.admin.pk}/').status_code, 403)


class RolesTests(BaseUsuariosTest):
    def _permiso(self, rol_etiqueta, codigo):
        tipo, _ = TipoUsuario.objects.get_or_create(tipo=rol_etiqueta)
        permiso, _ = Permiso.objects.get_or_create(permiso=codigo, tipo_usuario=tipo)
        return permiso

    def test_admin_asigna_rol_y_queda_auditado(self):
        permiso = self._permiso('Bacteriólogo', 'permiso_bacteriologo')
        self.client.force_authenticate(self.admin)
        r = self.client.post('/usr/usuarios-permisos/', {'usuario': self.sin_rol.pk, 'permiso': permiso.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(Auditoria.objects.filter(accion='rol.asignar', entidad_id=str(self.sin_rol.pk)).exists())
        self.assertEqual(self.login('sinrol').data['roles'], ['bacteriologo'])

    def test_usuario_no_modifica_sus_propios_roles(self):
        permiso = self._permiso('Bacteriólogo', 'permiso_bacteriologo')
        self.client.force_authenticate(self.admin)
        r = self.client.post('/usr/usuarios-permisos/', {'usuario': self.admin.pk, 'permiso': permiso.pk}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_medico_no_asigna_roles(self):
        permiso = self._permiso('Administrador', 'permiso_administrador')
        self.client.force_authenticate(self.medico)
        r = self.client.post('/usr/usuarios-permisos/', {'usuario': self.medico.pk, 'permiso': permiso.pk}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_varios_roles_suman_acciones(self):
        from .testing import asignar_rol
        asignar_rol(self.medico, 'bacteriologo')
        acciones = self.login('medico1').data['acciones']
        self.assertIn('ordenes.crear', acciones)
        self.assertIn('examenes.aprobar', acciones)

    def test_superusuario_no_tiene_acciones_clinicas(self):
        from django.contrib.auth import get_user_model
        su = get_user_model().objects.create_superuser('root', 'r@x.co', CONTRASENA_PRUEBA)
        acciones = self.login('root').data['acciones']
        self.assertIn('usuarios.gestionar', acciones)
        self.assertNotIn('examenes.aprobar', acciones)
        self.assertNotIn('ordenes.crear', acciones)


class PerfilPropioTests(BaseUsuariosTest):
    def test_ver_perfil_con_roles_y_acciones(self):
        self.client.force_authenticate(self.bacteriologo)
        r = self.client.get('/usr/me/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['roles'], ['bacteriologo'])
        self.assertIn('examenes.aprobar', r.data['acciones'])
        self.assertNotIn('password', r.data)

    def test_no_puede_cambiar_username_ni_roles(self):
        self.client.force_authenticate(self.medico)
        r = self.client.patch('/usr/me/', {'username': 'hack', 'telefono': '3001234567'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.medico.refresh_from_db()
        self.assertEqual(self.medico.username, 'medico1')
        self.assertEqual(self.medico.telefono, '3001234567')
        self.assertEqual(UsuarioXPermiso.objects.filter(usuario=self.medico).count(), 1)

    def test_cambio_de_contrasena_exige_la_actual(self):
        self.client.force_authenticate(self.medico)
        r = self.client.post('/usr/me/password/', {'password_actual': 'mala', 'password_nueva': 'Otra-Clave-2026!'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/usr/me/password/', {'password_actual': CONTRASENA_PRUEBA, 'password_nueva': 'Otra-Clave-2026!'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.login('medico1', password='Otra-Clave-2026!').status_code, 200)


class DispositivosTests(BaseUsuariosTest):
    def test_cada_usuario_ve_solo_sus_dispositivos(self):
        self.login('medico1', device_id='dev-medico')
        self.login('bact1', device_id='dev-bact')
        self.client.force_authenticate(self.medico)
        ids = {d['device_id'] for d in self.client.get('/usr/dispositivos-confianza/').data}
        self.assertEqual(ids, {'dev-medico'})
        self.client.force_authenticate(self.admin)
        ids = {d['device_id'] for d in self.client.get('/usr/dispositivos-confianza/').data}
        self.assertEqual(ids, {'dev-medico', 'dev-bact'})


class CatalogosTests(BaseUsuariosTest):
    def test_cualquier_rol_lee_y_solo_admin_escribe(self):
        self.client.force_authenticate(self.medico)
        self.assertEqual(self.client.get('/usr/departamentos/').status_code, 200)
        self.assertEqual(self.client.post('/usr/departamentos/', {'codigo': '25', 'departamento': 'Cundinamarca'}).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post('/usr/departamentos/', {'codigo': '25', 'departamento': 'Cundinamarca'}).status_code, 201)
