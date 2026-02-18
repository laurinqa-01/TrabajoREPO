from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from firebase_admin import firestore, auth
from config.firebase_connection import initialize_firebase
from functools import wraps
import requests
import os

# inicializar la base de datos con firestore
db = initialize_firebase()

def registro_usuario(request):
    mensaje = None
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            # vamos a crear en firebase auth
            user = auth.create_user(
                email=email,
                password=password
            )

            # crear en firestore (perfil del vendedor/administrador)
            db.collection('perfiles').document(user.uid).set({
                'email': email,
                'uid': user.uid,
                'rol': 'vendedor',
                'fecha_registro': firestore.SERVER_TIMESTAMP,
            })

            mensaje = f"Vendedor registrado correctamente con UID: {user.uid}"

        except Exception as e:
            mensaje = f"error: {e}"

    return render(request, 'registro.html', {'mensaje': mensaje})

# decorador de seguridad
def login_required_firebase(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'uid' not in request.session:
            messages.warning(request, " ⚠️ Warning, no has iniciado sesión ")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def iniciar_sesion(request):
    if ('uid') in request.session:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        api_key = os.getenv('FIREBASE_WEB_API_KEY')

        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"

        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        try:
            response = requests.post(url, json=payload)
            data = response.json()

            if response.status_code == 200:
                request.session['uid'] = data["localId"]
                request.session['email'] = data["email"]
                request.session['idToken'] = data["idToken"]
                messages.success(request, f"✅ Acceso correcto a la Tienda de Ropa")
                return redirect('dashboard')
            else:
                error_message = data.get('error', {}).get('message', 'UNKNOWN_ERROR')
                errores_comunes = {
                    'INVALID_LOGIN_CREDENTIALS': 'La contraseña es incorrecta o el correo no es válido.',
                    'EMAIL_NOT_FOUND': 'Este correo no está registrado.',
                    'USER_DISABLED': 'Esta cuenta ha sido inhabilitada.',
                    'TOO_MANY_ATTEMPTS_TRY_LATER': 'Demasiados intentos. Espere unos minutos.'
                }
                mensaje_usuario = errores_comunes.get(error_message, "Error de autenticacion")
                messages.error(request, mensaje_usuario)

        except requests.exceptions.RequestException as e:
            messages.error(request, "Error de conexión con el servidor")
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")

    return render(request, 'login.html')

def cerrar_sesion(request):
    request.session.flush()
    messages.info(request, "Has cerrado sesión correctamente")
    return redirect('login')

@login_required_firebase
def dashboard(request):
    uid = request.session.get('uid')
    datos_usuario = {}

    try:
        doc_ref = db.collection('perfiles').document(uid)
        doc = doc_ref.get()

        if doc.exists:
            datos_usuario = doc.to_dict()
        else:
            datos_usuario = {
                'email': request.session.get('email'),
                'uid': request.session.get('uid'),
                'rol': 'vendedor',
                'fecha_registro': firestore.SERVER_TIMESTAMP,
            }

    except Exception as e:
        messages.error(request, f"Error al cargar los datos: {e}")
    return render(request, 'dashboard.html', {'datos': datos_usuario})

@login_required_firebase
def listar_productos(request):
    """
    READ: recuperar las prendas de ropa registradas
    """
    uid = request.session.get('uid')
    productos = []

    try:
        # Filtramos los productos creados por este usuario (vendedor)
        docs = db.collection('productos').where('usuario_id', '==', uid).stream()
        for doc in docs:
            producto = doc.to_dict()
            producto['id'] = doc.id
            productos.append(producto) # Corregido: antes tenías tarea.append(tarea)
    except Exception as e:
        messages.error(request, f"Hubo un error al obtener el catálogo: {e}")

    return render(request, 'tienda/listar.html', {'productos': productos})

@login_required_firebase
def agregar_producto(request):
    """
    CREATE: registrar una nueva prenda de ropa
    """
    if (request.method == 'POST'):
        nombre = request.POST.get('nombre')
        talla = request.POST.get('talla')
        precio = request.POST.get('precio')
        uid = request.session.get('uid')

        try:
            db.collection('productos').add({
                'nombre': nombre,
                'talla': talla,
                'precio': precio,
                'usuario_id': uid,
                'fecha_registro': firestore.SERVER_TIMESTAMP
            })
            messages.success(request, "Prenda agregada al inventario")
            return redirect('listar_productos')
        except Exception as e:
            messages.error(request, f"Error al agregar producto: {e}")

    return render(request, 'tienda/form.html')

@login_required_firebase
def eliminar_producto(request, producto_id):
    """
    DELETE: eliminar una prenda por ID
    """
    try:
        db.collection('productos').document(producto_id).delete()
        messages.success(request, "Producto eliminado del inventario")
    except Exception as e:
        messages.error(request, f"Error al eliminar: {e}")

    return redirect('listar_productos')

@login_required_firebase
def editar_producto(request, producto_id):
    """
    UPDATE: Actualizar datos de una prenda (precio, talla, etc.)
    """
    uid = request.session.get('uid')
    producto_ref = db.collection('productos').document(producto_id)

    try:
        doc = producto_ref.get()
        if not doc.exists:
            messages.error(request, "El producto no existe")
            return redirect('listar_productos')

        producto_data = doc.to_dict()

        if producto_data.get('usuario_id') != uid:
            messages.error(request, "No tienes permiso para editar este producto")
            return redirect('listar_productos')

        if request.method == 'POST':
            nuevo_nombre = request.POST.get('nombre')
            nueva_talla = request.POST.get('talla')
            nuevo_precio = request.POST.get('precio')

            producto_ref.update({
                'nombre': nuevo_nombre,
                'talla': nueva_talla,
                'precio': nuevo_precio,
                'fecha_actualizacion': firestore.SERVER_TIMESTAMP
            })

            messages.success(request, "Producto actualizado con éxito")
            return redirect('listar_productos')

    except Exception as e:
        messages.error(request, f"Error al editar el producto: {e}")
        return redirect('listar_productos')

    return render(request, 'tienda/editar.html', {'producto': producto_data, 'id': producto_id})
