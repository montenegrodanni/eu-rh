from flask import render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets

from services.database import get_db_connection


def register_auth_routes(app, enviar_email_recuperacao):

    @app.route('/login', methods=['GET', 'POST'])
    def pagina_login():
        erro = None

        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            senha = request.form.get('senha', '').strip()

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM empresas WHERE email = ?", (email,))
            empresa = cursor.fetchone()

            conn.close()

            if empresa and check_password_hash(empresa['senha'], senha):
                session['empresa_id'] = empresa['id']
                session['empresa_nome'] = empresa['nome']
                return redirect(url_for('dashboard'))
            else:
                erro = "Email ou senha inválidos"

        return render_template('login.html', erro=erro)


    @app.route('/cadastro', methods=['GET', 'POST'])
    def cadastro():
        if request.method == 'POST':
            nome = request.form.get('empresa')
            email = request.form.get('email')
            senha_digitada = request.form.get('senha')
            confirmar = request.form.get('confirmar_senha')

            if senha_digitada != confirmar:
                return render_template('cadastro.html', erro="As senhas não coincidem")

            senha = generate_password_hash(senha_digitada)

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM empresas WHERE email = ?", (email,))
            empresa_existente = cursor.fetchone()

            if empresa_existente:
                conn.close()
                return render_template('cadastro.html', erro="Email já cadastrado")

            cursor.execute("""
                INSERT INTO empresas (nome, email, senha)
                VALUES (?, ?, ?)
            """, (nome, email, senha))

            conn.commit()
            conn.close()

            return redirect(url_for('pagina_login'))

        return render_template('cadastro.html')


    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('home'))


    @app.route('/esqueci-senha', methods=['GET', 'POST'])
    def esqueci_senha():
        mensagem = None
        erro = None

        if request.method == 'POST':
            email = request.form.get('email')

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT id, nome, email FROM empresas WHERE email = ?', (email,))
            empresa = cursor.fetchone()

            if empresa:
                empresa_id = empresa['id']
                token = secrets.token_urlsafe(32)
                expiracao = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('DELETE FROM recuperacao_senha WHERE empresa_id = ?', (empresa_id,))
                cursor.execute('''
                    INSERT INTO recuperacao_senha (empresa_id, token, expiracao)
                    VALUES (?, ?, ?)
                ''', (empresa_id, token, expiracao))

                conn.commit()

                link_reset = url_for('redefinir_senha', token=token, _external=True)

                try:
                    enviar_email_recuperacao(
                        destinatario=empresa['email'],
                        nome_empresa=empresa['nome'],
                        link_reset=link_reset
                    )
                    mensagem = 'Enviamos as instruções de redefinição para o seu email.'
                except Exception as e:
                    erro = f'Não foi possível enviar o email: {str(e)}'
            else:
                erro = 'Email não encontrado no sistema.'

            conn.close()

        return render_template('esqueci_senha.html', mensagem=mensagem, erro=erro)


    @app.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
    def redefinir_senha(token):
        erro = None
        mensagem = None

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT empresa_id, expiracao
            FROM recuperacao_senha
            WHERE token = ?
        ''', (token,))
        registro = cursor.fetchone()

        if not registro:
            conn.close()
            return 'Token inválido ou não encontrado.'

        empresa_id = registro['empresa_id']
        expiracao = registro['expiracao']
        expiracao_dt = datetime.strptime(expiracao, '%Y-%m-%d %H:%M:%S')

        if datetime.now() > expiracao_dt:
            cursor.execute('DELETE FROM recuperacao_senha WHERE token = ?', (token,))
            conn.commit()
            conn.close()
            return 'Este link expirou.'

        if request.method == 'POST':
            senha = request.form.get('senha')
            confirmar_senha = request.form.get('confirmar_senha')

            if not senha or not confirmar_senha:
                erro = 'Preencha todos os campos.'
            elif senha != confirmar_senha:
                erro = 'As senhas não coincidem.'
            else:
                nova_senha_hash = generate_password_hash(senha)

                cursor.execute('UPDATE empresas SET senha = ? WHERE id = ?', (nova_senha_hash, empresa_id))
                cursor.execute('DELETE FROM recuperacao_senha WHERE token = ?', (token,))
                conn.commit()
                conn.close()

                return redirect(url_for('pagina_login'))

        conn.close()
        return render_template('redefinir_senha.html', erro=erro, mensagem=mensagem)