$(function() {
  function getCart() {
    try { return JSON.parse(localStorage.getItem('cart') || '[]'); }
    catch (e) { return []; }
  }
  function saveCart(cart) { localStorage.setItem('cart', JSON.stringify(cart)); }
  function formatPrice(num) {
    return Number(num || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  function showToast(message) {
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.id = 'toast-container';
      toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
      document.body.appendChild(toastContainer);
    }
    const el = document.createElement('div');
    el.className = 'toast align-items-center text-bg-success border-0';
    el.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>`;
    toastContainer.appendChild(el);
    new bootstrap.Toast(el).show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
  }

  function renderCart() {
    const $container = $('#carrinhoItens');
    if ($container.length === 0) return;

    const cart = getCart();
    $container.empty();

    if (!cart.length) {
      $container.html('<p class="text-center text-muted">Carrinho vazio.</p>');
      $('#totalCarrinho').text(formatPrice(0));
      return;
    }

    cart.forEach(item => {
      const line = item.price * item.qty;
      const $row = $(`
        <div class="col-12">
          <div class="card p-3 d-flex flex-row align-items-center justify-content-between" data-id="${item.id}">
            <div class="d-flex align-items-center">
              <img src="${item.img}" alt="${item.title}" style="width:65px" class="me-3">
              <div>
                <h5 class="mb-1">${item.title}</h5>
                <p class="mb-0">
                  Quantidade: 
                  <input type="number" class="form-control form-control-sm qty-input" 
                         value="${item.qty}" min="1" style="width:80px; display:inline-block;">
                  | Unitário: ${formatPrice(item.price)}
                </p>
              </div>
            </div>
            <div class="d-flex align-items-center">
              <span class="ms-3 fw-bold subtotal">Subtotal: ${formatPrice(line)}</span>
              <a href="#" class="text-danger ms-3 remove-item">Remover</a>
            </div>
          </div>
        </div>
      `);

      $container.append($row);

      $row.find('.qty-input').on('input', function() {
        const newQty = Math.max(1, parseInt($(this).val(), 10) || 1);
        const id = $(this).closest('[data-id]').data('id');

        const cart = getCart();
        const item = cart.find(it => it.id === id);
        if (item) {
          item.qty = newQty;
          saveCart(cart);

          const newLine = item.price * item.qty;
          $row.find('.subtotal').text(`Subtotal: ${formatPrice(newLine)}`);
          updateTotals();
        }
      });
    });

    updateTotals();

    $('.remove-item').on('click', function(e){
      e.preventDefault();
      const id = $(this).closest('[data-id]').data('id');
      const cart = getCart().filter(it => it.id !== id);
      saveCart(cart);
      renderCart();
    });
  }

  function updateTotals() {
    const cart = getCart();
    const subtotal = cart.reduce((sum, i) => sum + (i.price * i.qty), 0);
    $('#totalCarrinho').text(formatPrice(subtotal));
  }

  $(document).on('click', '.btn-addcart, .btn-carrinho', function(e) {
    e.preventDefault();

    let title, price, img, id;

    const $card = $(this).closest('.card');
    if ($card.length) {
      title = $card.find('.product-title').text().trim();
      const priceText = ($card.find('.text-success').text() || '').trim();
      const cleaned = priceText.replace(/[^0-9,.-]+/g, '').replace(/\./g, '').replace(',', '.');
      price = parseFloat(cleaned);
      img = $card.find('img.card-img-top').attr('src') || '';
    } else {
      title = $('.titulo-produto').text().trim();
      const priceText = ($('.preco-produto').text() || '').trim();
      const cleaned = priceText.replace(/[^0-9,.-]+/g, '').replace(/\./g, '').replace(',', '.');
      price = parseFloat(cleaned);
      img = $('main img').attr('src') || '';
    }

    id = title.replace(/\s+/g, '-').toLowerCase();

    const cart = getCart();
    const existing = cart.find(it => it.id === id);
    if (existing) {
      existing.qty += 1;
    } else {
      cart.push({ id, title, price, img, qty: 1 });
    }
    saveCart(cart);

    showToast('Produto adicionado ao carrinho!');
    renderCart();
  });

  $('#apagarCarrinho').on('click', function(){
    localStorage.removeItem('cart');
    renderCart();
  });

  $('#checkout-button').on('click', function() {
    const cart = getCart();
    const user = JSON.parse(localStorage.getItem('usuario_logado') || '{}');

    if (!cart.length) {
      alert('Seu carrinho está vazio');
      return;
    }

    if (!user || !user.id) {
      alert('Você precisa fazer login para finalizar a compra');
      return;
    }

    const total = cart.reduce((sum, i) => sum + (i.price * i.qty), 0);

    $.ajax({
      url: 'http://localhost:3000/checkout',
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        usuario_id: user.id,
        cart: cart,
        total: total
      }),
      success: function(data) {
        if (data.success) {
          alert('Compra realizada com sucesso! Pedido Número ' + data.pedidoID);
          localStorage.removeItem('cart');
          window.location.href = 'index.html';
        } else {
          alert('Erro ao processar a compra. Tente novamente');
        }
      },
      error: function(xhr, status, error) {
        console.error(error);
        alert('Erro no servidor ao processar a compra');
      }
    });
  });

  renderCart();
});
