document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.querySelector('.search-input');
  const infoRodape = document.getElementById("info-pesquisa");
  const resultsRow = document.getElementById("search-results");

  const removeAcentos = str => str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");


  const allCols = document.querySelectorAll('.product-list .col-5th');
  allCols.forEach(col => {
    const parent = col.parentElement;
    if (!parent.id) parent.id = 'pl-' + Math.random().toString(36).slice(2,8);
    col.dataset.parentId = parent.id;
  });

  function restoreAll() {
 
  const movedCols = document.querySelectorAll('#search-results .col-5th');
    movedCols.forEach(col => {
      const parent = document.getElementById(col.dataset.parentId);
      if (parent) parent.appendChild(col);
    });
    resultsRow.innerHTML = '';
    if (infoRodape) infoRodape.textContent = '';

    document.querySelectorAll('.product-list .col-5th').forEach(col => col.style.display = '');
  }

  if (searchInput) {
    searchInput.addEventListener('keyup', event => {
      const searchTerm = removeAcentos(event.target.value.toLowerCase().trim());

      if (searchTerm === '') {
        restoreAll();
        return;
      }

      infoRodape.textContent = `Você pesquisou por: "${searchTerm}"`;

     
      const existingResults = document.querySelectorAll('#search-results .col-5th');
      existingResults.forEach(col => {
        const parent = document.getElementById(col.dataset.parentId);
        if (parent) parent.appendChild(col);
      });
      resultsRow.innerHTML = '';

      const products = document.querySelectorAll('.product-list .product-item');
      let foundCount = 0;

      products.forEach(product => {
        const titleEl = product.querySelector('.product-title');
        const col = product.closest('.col-5th');
        if (!titleEl || !col) return;

        const productName = removeAcentos(titleEl.textContent.toLowerCase());

        let match = false;
        if (searchTerm === "pc" || searchTerm === "computador") {
          match = productName.includes("pc") || productName.includes("computador");
        } else {
          match = productName.includes(searchTerm);
        }

        if (match) {
          resultsRow.appendChild(col); 
          col.style.display = '';
          foundCount++;
        } else {
          col.style.display = 'none';
        }
      });

      if (foundCount === 0) {
        resultsRow.innerHTML = '<div class="col-12 text-muted">Nenhum produto encontrado.</div>';
      }
    });
  }
});