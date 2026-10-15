const titulo = document.querySelector('.titulo-animado');
const textoTitulo = titulo.textContent;
const letras = textoTitulo.split('');
titulo.textContent = '';
letras.forEach((letra) => {
    const span = document.createElement('span');
    span.textContent = letra;
    span.className = 'letra';
    titulo.appendChild(span);
});