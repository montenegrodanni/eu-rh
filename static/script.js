document.addEventListener("DOMContentLoaded", function () {
    // =========================
    // 1. FLASH SUMINDO SOZINHO
    // =========================
    const flashes = document.querySelectorAll(".flash");

    if (flashes.length > 0) {
        setTimeout(() => {
            flashes.forEach(flash => {
                flash.style.opacity = "0";
                flash.style.transform = "translateY(-10px)";

                setTimeout(() => {
                    flash.style.display = "none";
                }, 400);
            });
        }, 3000);
    }

    // =========================
    // 2. LOADING EM FORMULÁRIOS
    // =========================
    const forms = document.querySelectorAll("form");

    forms.forEach(form => {
        form.addEventListener("submit", function () {
            const botao = form.querySelector('button[type="submit"], input[type="submit"]');

            if (botao) {
                if (botao.tagName.toLowerCase() === "button") {
                    botao.dataset.textoOriginal = botao.innerHTML;
                    botao.innerHTML = "Carregando...";
                } else {
                    botao.dataset.textoOriginal = botao.value;
                    botao.value = "Carregando...";
                }

                botao.disabled = true;
                botao.style.opacity = "0.7";
                botao.style.cursor = "not-allowed";
            }
        });
    });

    // =========================
    // 3. ANIMAÇÃO SUAVE AO ENTRAR
    // =========================
    const blocosAnimados = document.querySelectorAll(
        ".cadastro-card, .cadastro-texto, .login-box, .card-resumo, .vaga-card, .candidato-card"
    );

    blocosAnimados.forEach((bloco, index) => {
        bloco.style.opacity = "0";
        bloco.style.transform = "translateY(20px)";
        bloco.style.transition = "all 0.5s ease";

        setTimeout(() => {
            bloco.style.opacity = "1";
            bloco.style.transform = "translateY(0)";
        }, 100 + index * 100);
    });
});