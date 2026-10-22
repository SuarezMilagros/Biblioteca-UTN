// Mejoras pequeñas de interfaz. Si este archivo no carga, el sitio sigue funcionando.

document.addEventListener('DOMContentLoaded', () => {
    // Si el formulario tiene errores, el cursor queda en el primer campo con error.
    const primerCampoConError = document.querySelector(
        '.campo-error input, .campo-error select, .campo-error textarea'
    );
    if (primerCampoConError) {
        primerCampoConError.focus();
    }

    // Evita que un doble clic en "Guardar" envíe el formulario dos veces.
    document.querySelectorAll('form.formulario').forEach((formulario) => {
        formulario.addEventListener('submit', () => {
            const boton = formulario.querySelector('button[type="submit"]');
            if (boton) {
                // Se deshabilita en el siguiente turno, cuando el envío ya está en curso.
                setTimeout(() => {
                    boton.disabled = true;
                }, 0);
            }
        });
    });
});

// Al volver con el botón "atrás", el navegador puede mostrar el botón deshabilitado: se vuelve a habilitar.
window.addEventListener('pageshow', () => {
    document.querySelectorAll('form.formulario button[type="submit"]').forEach((boton) => {
        boton.disabled = false;
    });
});