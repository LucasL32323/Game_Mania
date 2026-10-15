$(document).ready(function(){
    const user = JSON.parse(localStorage.getItem('Usuario logado'));
    if(!user){
        window.location.href = "entreoucadastrese.html";
        return;
    }

    $('#perfil-nome').text(user.nome);
    $('#perfil-email').text(user.email);

    $('#tab-dados').click(function(e){
        e.preventDefault();
        $(this).addClass('active').siblings().removeClass('active');
        $('#content-dados').removeClass('d-none');  
        $('#content-pedidos').addClass('d-none');
    });

    $('#tab-pedidos').click(function(e){
        e.preventDefault();
        $(this).addClass('active').siblings().removeClass('active');
        $('#content-dados').addClass('d-none');
        $('#content-pedidos').removeClass('d-none');
        carregarPedidos();
    });

    function carregarPedidos(){
        $.ajax({
            url: `http://localhost:3000/meus-pedidos/${user.id}`,
            method: 'GET',
            success: function(pedidos){
                const $lista = $('#lista-pedidos');
                $lista.empty();
                if(pedidos.length === 0) {
                    $lista.html('<p class="alert alert-info">Nenhum pedido encontrado.</p>');
                    return;
                }

                pedidos.forEach(p => {
                    const data = new Date(p.data_pedido).toLocaleDateString('pt-BR');
                    const valor = parseFloat(p.valor_total).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
                    $lista.append(`
                        <div class="card mb-3">
                            <div class="card-body">
                                <h5 class="card-title">Pedido ${p.id}</h5>
                                <p class="card-text">
                                    Data: ${data}<br>
                                    Status: <strong>${p.status}</strong><br>
                                    Total: <span class="text-success fw-bold">${valor}</span>
                                </p>
                            </div>
                        </div>
                    `);
                });
            }
        });
    }
});
