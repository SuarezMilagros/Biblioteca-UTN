// Mejoras de interfaz de SIGEBI. Todo es mejora progresiva: si este archivo no carga,
// el sistema sigue funcionando (los formularios se envían igual y el menú se ve completo).

document.addEventListener('DOMContentLoaded', () => {
    // ---------- Foco en el primer campo con error ----------
    const primerCampoConError = document.querySelector(
        '.campo-error input, .campo-error select, .campo-error textarea'
    );
    if (primerCampoConError) {
        primerCampoConError.focus();
    }

    // ---------- Menú lateral en pantallas chicas ----------
    const app = document.getElementById('app');
    const botonMenu = document.querySelector('.boton-menu');
    const abrirMenu = (abierto) => {
        if (!app || !botonMenu) return;
        app.classList.toggle('menu-abierto', abierto);
        botonMenu.setAttribute('aria-expanded', String(abierto));
        if (abierto) {
            const primerEnlace = document.querySelector('.lateral .nav-enlace');
            if (primerEnlace) primerEnlace.focus();
        } else {
            botonMenu.focus();
        }
    };
    if (botonMenu) {
        botonMenu.addEventListener('click', () => abrirMenu(!app.classList.contains('menu-abierto')));
        document.querySelectorAll('[data-cerrar-menu]').forEach((elemento) => {
            elemento.addEventListener('click', () => abrirMenu(false));
        });
        document.addEventListener('keydown', (evento) => {
            if (evento.key === 'Escape' && app.classList.contains('menu-abierto')) abrirMenu(false);
        });
    }

    // ---------- Avisos que se pueden cerrar ----------
    document.querySelectorAll('[data-cerrar-mensaje]').forEach((boton) => {
        boton.hidden = false;
        boton.addEventListener('click', () => {
            const mensaje = boton.closest('.mensaje');
            if (mensaje) mensaje.remove();
        });
    });

    // ---------- Confirmación antes de acciones que retiran registros ----------
    // Un formulario con data-confirmar="texto" pide confirmación en un modal antes de enviarse.
    const modal = document.getElementById('modal-confirmar');
    let formularioPendiente = null;
    if (modal && typeof modal.showModal === 'function') {
        const aceptar = modal.querySelector('[data-modal-aceptar]');
        modal.querySelector('[data-modal-cancelar]').addEventListener('click', () => modal.close());
        aceptar.addEventListener('click', () => {
            const formulario = formularioPendiente;
            formularioPendiente = null;
            modal.close();
            if (formulario) {
                formulario.dataset.confirmado = 'si';
                formulario.requestSubmit();
            }
        });
        document.querySelectorAll('form[data-confirmar]').forEach((formulario) => {
            formulario.addEventListener('submit', (evento) => {
                if (formulario.dataset.confirmado === 'si') return;
                evento.preventDefault();
                formularioPendiente = formulario;
                document.getElementById('modal-titulo').textContent =
                    formulario.dataset.confirmarTitulo || 'Confirmar acción';
                document.getElementById('modal-texto').textContent = formulario.dataset.confirmar;
                aceptar.textContent = formulario.dataset.confirmarBoton || 'Confirmar';
                modal.showModal();
                aceptar.focus();
            });
        });
    }

    // ---------- Estado de carga y doble envío ----------
    // Evita que un doble clic en "Guardar" envíe el formulario dos veces y muestra que se está procesando.
    document.querySelectorAll('form.formulario').forEach((formulario) => {
        formulario.addEventListener('submit', (evento) => {
            if (evento.defaultPrevented) return;
            const boton = formulario.querySelector('button[type="submit"]');
            if (boton) {
                // Se deshabilita en el siguiente turno, cuando el envío ya está en curso.
                setTimeout(() => {
                    boton.disabled = true;
                    boton.classList.add('cargando');
                }, 0);
            }
        });
    });

    // ---------- Mostrar u ocultar la contraseña ----------
    document.querySelectorAll('[data-mostrar-clave]').forEach((boton) => {
        const campo = document.getElementById(boton.dataset.mostrarClave);
        if (!campo) return;
        boton.hidden = false;
        boton.addEventListener('click', () => {
            const visible = campo.type === 'text';
            campo.type = visible ? 'password' : 'text';
            boton.textContent = visible ? 'Mostrar' : 'Ocultar';
            boton.setAttribute('aria-pressed', String(!visible));
        });
    });

    // ---------- Buscador en listas desplegables largas (S6-11) ----------
    // Un <select data-buscador="Texto"> (ver con_buscador en biblioteca/forms.py) recibe un campo que
    // filtra sus opciones mientras se escribe, sin distinguir tildes ni mayúsculas. Si hay coincidencias
    // y la opción elegida no está entre ellas, se elige la primera. Sin JavaScript, la lista funciona igual.
    const normalizar = (texto) => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    document.querySelectorAll('select[data-buscador]').forEach((lista) => {
        const opciones = Array.from(lista.options).map((opcion) => ({ opcion, texto: normalizar(opcion.text) }));
        const buscador = document.createElement('input');
        buscador.type = 'search';
        buscador.className = 'buscador-lista';
        buscador.placeholder = `${lista.dataset.buscador}…`;
        buscador.autocomplete = 'off';
        buscador.setAttribute('aria-label', lista.dataset.buscador);
        const aviso = document.createElement('small');
        aviso.className = 'ayuda';
        aviso.id = `${lista.id}-coincidencias`;
        aviso.setAttribute('role', 'status');
        buscador.setAttribute('aria-describedby', aviso.id);
        lista.before(buscador);
        lista.after(aviso);

        // Enter no envía el formulario: pasa a la lista para elegir entre las coincidencias.
        buscador.addEventListener('keydown', (evento) => {
            if (evento.key === 'Enter') {
                evento.preventDefault();
                lista.focus();
            }
        });
        buscador.addEventListener('input', () => {
            const termino = normalizar(buscador.value.trim());
            const visibles = termino
                ? opciones.filter((item) => item.opcion.value !== '' && item.texto.includes(termino))
                : opciones;
            if (visibles.length === 0) {
                aviso.textContent = 'Sin coincidencias: la lista no cambió.';
                return;
            }
            const valorAnterior = lista.value;
            lista.replaceChildren(...visibles.map((item) => item.opcion));
            if (visibles.some((item) => item.opcion.value === valorAnterior)) {
                lista.value = valorAnterior;
            } else {
                lista.value = visibles[0].opcion.value;
                lista.dispatchEvent(new Event('change', { bubbles: true }));
            }
            aviso.textContent = termino
                ? `${visibles.length} ${visibles.length === 1 ? 'coincidencia' : 'coincidencias'}. Elegido: ${lista.selectedOptions[0].text}.`
                : '';
        });
    });

    // ---------- Vista previa del libro (portada, título y autor) ----------
    const vistaPrevia = document.querySelector('[data-vista-previa]');
    if (vistaPrevia) {
        const titulo = document.getElementById('id_titulo');
        const autor = document.getElementById('id_autor');
        const imagen = document.getElementById('id_imagen');
        const salidaTitulo = vistaPrevia.querySelector('[data-previa-titulo]');
        const salidaAutor = vistaPrevia.querySelector('[data-previa-autor]');
        const salidaPortada = vistaPrevia.querySelector('[data-previa-portada]');
        const actualizarTexto = () => {
            if (titulo && salidaTitulo) salidaTitulo.textContent = titulo.value.trim() || 'Título del libro';
            if (autor && salidaAutor) {
                const opcion = autor.options[autor.selectedIndex];
                salidaAutor.textContent = opcion && autor.value ? opcion.text : 'Autor';
            }
        };
        if (titulo) titulo.addEventListener('input', actualizarTexto);
        if (autor) autor.addEventListener('change', actualizarTexto);
        actualizarTexto();
        if (imagen && salidaPortada) {
            imagen.addEventListener('change', () => {
                const archivo = imagen.files && imagen.files[0];
                if (!archivo || !archivo.type.startsWith('image/')) return;
                const lector = new FileReader();
                lector.onload = () => {
                    const img = document.createElement('img');
                    img.className = 'portada';
                    img.alt = 'Vista previa de la portada';
                    img.src = lector.result;
                    salidaPortada.replaceChildren(img);
                };
                lector.readAsDataURL(archivo);
            });
        }
    }
});

// Al volver con el botón "atrás", el navegador puede mostrar el botón deshabilitado: se vuelve a habilitar.
window.addEventListener('pageshow', () => {
    document.querySelectorAll('form.formulario button[type="submit"]').forEach((boton) => {
        boton.disabled = false;
        boton.classList.remove('cargando');
    });
});
