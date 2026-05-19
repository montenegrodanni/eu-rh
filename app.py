from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import sqlite3
from flask import flash
import os
import secrets
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from services.database import get_db_connection

app = Flask(__name__)
app.secret_key = 'eurh_chave_secreta'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'banco.db')

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg'}

# Preencha com seus dados reais
app.config['EMAIL_REMETENTE'] = 'SEU_EMAIL_AQUI'
app.config['EMAIL_SENHA'] = 'SUA_SENHA_DE_APP_AQUI'
app.config['SMTP_SERVIDOR'] = 'smtp.gmail.com'
app.config['SMTP_PORTA'] = 587


def conectar_banco():
    conn = get_db_connection()
    cursor = conn.cursor()


def arquivo_permitido(nome_arquivo):
    return '.' in nome_arquivo and nome_arquivo.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def criar_banco():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            titulo TEXT,
            descricao TEXT,
            setor TEXT,
            salario REAL,
            tipo_contrato TEXT,
            localizacao TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidatos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaga_id INTEGER,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            telefone TEXT,
            curriculo TEXT,
            arquivo_curriculo TEXT,
            status TEXT DEFAULT 'Recebido',
            nacionalidade TEXT,
            escolaridade TEXT,
            idioma TEXT,
            cidade TEXT,
            estado TEXT,
            linkedin TEXT,
            pretensao_salarial TEXT,
            disponibilidade TEXT,
            experiencia TEXT,
            foto TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recuperacao_senha (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            token TEXT NOT NULL,
            expiracao TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()


criar_banco()


def enviar_email_recuperacao(destinatario, nome_empresa, link_reset):
    remetente = app.config['EMAIL_REMETENTE'].strip()
    senha = app.config['EMAIL_SENHA'].replace(' ', '').strip()
    servidor = app.config['SMTP_SERVIDOR']
    porta = app.config['SMTP_PORTA']

    assunto = 'Recuperação de senha - EU RH'

    corpo_html = f'''
    <html>
        <body>
            <h2>Recuperação de senha</h2>
            <p>Olá, {nome_empresa}.</p>
            <p>Clique no link abaixo para redefinir sua senha:</p>
            <p><a href="{link_reset}">{link_reset}</a></p>
        </body>
    </html>
    '''

    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo_html, 'html'))

    with smtplib.SMTP(servidor, porta, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(remetente, senha)
        smtp.send_message(msg)


def calcular_score(vaga, candidato):
    score = 0
    motivos = []

    descricao_vaga = (vaga['descricao'] or "").lower()
    localizacao_vaga = (vaga['localizacao'] or "").lower()

    escolaridade = (candidato['escolaridade'] or "").lower()
    idioma = (candidato['idioma'] or "").lower()
    cidade = (candidato['cidade'] or "").lower()
    pretensao_salarial = (candidato['pretensao_salarial'] or "").lower()
    disponibilidade = (candidato['disponibilidade'] or "").lower()
    experiencia = (candidato['experiencia'] or "").lower()

    if cidade and localizacao_vaga and cidade in localizacao_vaga:
        score += 15
        motivos.append("Localização compatível")

    if "pós" in escolaridade or "pos" in escolaridade:
        score += 20
        motivos.append("Pós-graduação")
    elif "superior" in escolaridade:
        score += 18
        motivos.append("Boa escolaridade")
    elif "técnico" in escolaridade or "tecnico" in escolaridade:
        score += 12
        motivos.append("Formação técnica")

    if "ingl" in idioma:
        score += 15
        motivos.append("Possui inglês")
    elif "espanh" in idioma:
        score += 8
        motivos.append("Possui espanhol")

    try:
        if pretensao_salarial and vaga['salario']:
            pret = float(
                pretensao_salarial
                .replace("r$", "")
                .replace("R$", "")
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )
            sal = float(vaga['salario'])

            if pret <= sal:
                score += 10
                motivos.append("Pretensão dentro da faixa")
            elif pret <= sal * 1.1:
                score += 5
                motivos.append("Pretensão próxima da faixa")
    except:
        pass

    if "imediata" in disponibilidade:
        score += 10
        motivos.append("Disponibilidade imediata")
    elif "15 dias" in disponibilidade or "quinze dias" in disponibilidade:
        score += 6
        motivos.append("Disponibilidade em até 15 dias")
    elif "30 dias" in disponibilidade:
        score += 3
        motivos.append("Disponibilidade em até 30 dias")

    palavras_chave = [
        "tributário", "tributario", "fiscal", "imposto", "impostos",
        "contábil", "contabil", "financeiro", "administrativo",
        "atendimento", "vendas", "rh", "recrutamento", "seleção",
        "estoque", "logística", "logistica", "excel", "planilhas"
    ]

    pontos_exp = 0
    for palavra in palavras_chave:
        if palavra in descricao_vaga and palavra in experiencia:
            pontos_exp += 6

    if pontos_exp > 0:
        motivos.append("Experiência alinhada com a vaga")

    if pontos_exp > 30:
        pontos_exp = 30

    score += pontos_exp

    if score > 100:
        score = 100

    return score, motivos


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/cadastro-empresa')
def cadastro_empresa():
    return redirect(url_for('cadastro'))


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('empresa')
        email = request.form.get('email')
        senha = generate_password_hash(request.form.get('senha'))
        confirmar = request.form.get('confirmar_senha')

        if request.form.get('senha') != confirmar:
            return render_template('cadastro.html', erro="As senhas não coincidem")

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


@app.route('/dashboard')
def dashboard():
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))

    empresa_id = session['empresa_id']

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM vagas WHERE empresa_id = ?', (empresa_id,))
    vagas = cursor.fetchall()

    cursor.execute('SELECT COUNT(*) as total FROM vagas WHERE empresa_id = ?', (empresa_id,))
    total_vagas = cursor.fetchone()['total']

    cursor.execute('''
        SELECT COUNT(*) as total
        FROM candidatos c
        JOIN vagas v ON c.vaga_id = v.id
        WHERE v.empresa_id = ?
    ''', (empresa_id,))
    total_candidatos = cursor.fetchone()['total']

    cursor.execute('''
        SELECT COUNT(*) as total
        FROM candidatos c
        JOIN vagas v ON c.vaga_id = v.id
        WHERE v.empresa_id = ? AND c.status = 'Aprovado'
    ''', (empresa_id,))
    aprovados = cursor.fetchone()['total']

    conn.close()

    return render_template(
        'dashboard.html',
        vagas=vagas,
        total_vagas=total_vagas,
        total_candidatos=total_candidatos,
        aprovados=aprovados,
        empresa_nome=session['empresa_nome']
    )

@app.route('/candidatos_empresa')
def candidatos_empresa():
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))
    
    status_atual = request.args.get('status')

    empresa_id = session['empresa_id']
    status = request.args.get('status')
    vaga_id = request.args.get('vaga_id')

    conn = conectar_banco()
    cursor = conn.cursor()

    query = '''
        SELECT c.*, v.titulo
        FROM candidatos c
        JOIN vagas v ON c.vaga_id = v.id
        WHERE v.empresa_id = ?
    '''

    params = [empresa_id]

    if vaga_id:
        query += " AND v.id = ?"
        params.append(vaga_id)

    if status:
        query += " AND c.status = ?"
        params.append(status)

    cursor.execute(query, tuple(params))

    candidatos = cursor.fetchall()
    conn.close()

    

    return render_template(
    'candidatos_empresa.html',
    candidatos=candidatos,
    status_atual=status_atual,
    mostrar_botao_voltar=True
)

@app.route('/login', methods=['GET', 'POST'])
def pagina_login():
    erro = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()

        conn = conectar_banco()
        cursor = conn.cursor()

        cursor.execute(
            'SELECT id, nome, senha FROM empresas WHERE email = ?',
            (email,)
        )
        empresa = cursor.fetchone()

        conn.close()

        if empresa and check_password_hash(empresa['senha'], senha):
            session['empresa_id'] = empresa['id']
            session['empresa_nome'] = empresa['nome']
            return redirect(url_for('dashboard'))
        else:
            erro = "Email ou senha inválidos"

    return render_template('login.html', erro=erro)

@app.route('/minhas-vagas')
def minhas_vagas():
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT * FROM vagas WHERE empresa_id = ? ORDER BY id DESC',
        (session['empresa_id'],)
    )
    vagas = cursor.fetchall()

    conn.close()

    return render_template('minhas_vagas.html', vagas=vagas)


@app.route('/criar-vaga', methods=['GET', 'POST'])
def criar_vaga():
    if "empresa_id" not in session:
        return redirect(url_for("pagina_login"))

    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        setor = request.form.get("setor")
        salario = request.form.get("salario")
        tipo_contrato = request.form.get("tipo_contrato")
        localizacao = request.form.get("localizacao")

        if not titulo or not descricao or not setor or not salario or not tipo_contrato or not localizacao:
            return "Preencha todos os campos obrigatórios"

        conn = conectar_banco()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO vagas 
            (empresa_id, titulo, descricao, setor, salario, tipo_contrato, localizacao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["empresa_id"],
            titulo,
            descricao,
            setor,
            salario,
            tipo_contrato,
            localizacao
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("criar_vaga.html", mostrar_botao_voltar=True)


@app.route('/editar-vaga/<int:id>')
def pagina_editar_vaga(id):
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM vagas WHERE id = ? AND empresa_id = ?', (id, session['empresa_id']))
    vaga = cursor.fetchone()

    conn.close()

    if not vaga:
        return 'Vaga não encontrada.'

    return render_template('editar_vaga.html', vaga=vaga)


@app.route('/editar-vaga/<int:id>', methods=['POST'])
def editar_vaga(id):
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))

    titulo = request.form.get('titulo')
    descricao = request.form.get('descricao')
    setor = request.form.get('setor')
    salario = request.form.get('salario')
    tipo_contrato = request.form.get('tipo_contrato')
    localizacao = request.form.get('localizacao')

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE vagas
        SET titulo = ?, descricao = ?, setor = ?, salario = ?, tipo_contrato = ?, localizacao = ?
        WHERE id = ? AND empresa_id = ?
    ''', (titulo, descricao, setor, salario, tipo_contrato, localizacao, id, session['empresa_id']))

    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))


@app.route('/excluir-vaga/<int:id>')
def excluir_vaga(id):
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM vagas WHERE id = ? AND empresa_id = ?', (id, session['empresa_id']))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/vagas')
def listar_vagas():
    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT v.id, v.titulo, v.descricao, v.setor, v.salario, v.tipo_contrato, v.localizacao, e.nome
        FROM vagas v
        JOIN empresas e ON v.empresa_id = e.id
        ORDER BY v.id DESC
    ''')
    vagas = cursor.fetchall()

    conn.close()

    return render_template('vagas.html', vagas=vagas)


@app.route('/vaga/<int:id>')
def ver_vaga_publica(id):
    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM vagas WHERE id = ?', (id,))
    vaga = cursor.fetchone()

    conn.close()

    if not vaga:
        return 'Vaga não encontrada.'

    return render_template('vaga_publica.html', vaga=vaga)


@app.route('/vaga/<int:id>/candidatar', methods=['GET', 'POST'])
def candidatar(id):

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM vagas WHERE id = ?", (id,))
    vaga = cursor.fetchone()

    if request.method == 'POST':

        nome = request.form.get('nome')
        email = request.form.get('email')

        tipo_contrato = request.form.get('tipo_contrato')
        modelo = request.form.get('modelo')
        turno = request.form.get('turno')

        print(tipo_contrato, modelo, turno)

        arquivo = request.files.get('arquivo_curriculo')
        nome_arquivo = None

        if arquivo and arquivo.filename != '':
            extensao = arquivo.filename.rsplit('.', 1)[1].lower() if '.' in arquivo.filename else ''
            if extensao == 'pdf':
                nome_seguro = secure_filename(arquivo.filename)
                nome_arquivo = f'{id}_{nome_seguro}'
                caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                arquivo.save(caminho_arquivo)
            else:
                return 'Envie apenas arquivos PDF no currículo.'
            
            

        foto = request.files.get('foto')
        foto_nome = None

        if foto and foto.filename != '':
            extensao_foto = foto.filename.rsplit('.', 1)[1].lower() if '.' in foto.filename else ''
            if extensao_foto in {'png', 'jpg', 'jpeg'}:
                nome_foto = secure_filename(foto.filename)
                foto_nome = f'foto_{id}_{nome_foto}'
                caminho_foto = os.path.join(app.config['UPLOAD_FOLDER'], foto_nome)
                foto.save(caminho_foto)
            else:
                return 'Envie a foto em PNG, JPG ou JPEG.'

        conn.close()
        return render_template('sucesso.html', vaga_id=id)

    conn.close()
    return render_template('candidatar.html', vaga=vaga)


@app.route('/vaga/<int:vaga_id>/candidatos')
def ver_candidatos(vaga_id):
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))

    empresa_id = session['empresa_id']
    status_filtro = request.args.get('status', 'Todos')

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM vagas WHERE id = ? AND empresa_id = ?', (vaga_id, empresa_id))
    vaga = cursor.fetchone()

    if not vaga:
        conn.close()
        return "Vaga não encontrada."

    cursor.execute('''
        SELECT status, COUNT(*) as total
        FROM candidatos
        WHERE vaga_id = ?
        GROUP BY status
    ''', (vaga_id,))
    contagem_status_db = cursor.fetchall()

    contagem_status = {
        'Recebido': 0,
        'Em análise': 0,
        'Entrevista': 0,
        'Aprovado': 0,
        'Reprovado': 0
    }

    for row in contagem_status_db:
        contagem_status[row['status']] = row['total']

    total_candidatos = sum(contagem_status.values())

    if status_filtro == 'Todos':
        cursor.execute('''
            SELECT * FROM candidatos
            WHERE vaga_id = ?
            ORDER BY id DESC
        ''', (vaga_id,))
        candidatos_db = cursor.fetchall()
    else:
        cursor.execute('''
            SELECT * FROM candidatos
            WHERE vaga_id = ? AND status = ?
            ORDER BY id DESC
        ''', (vaga_id, status_filtro))
        candidatos_db = cursor.fetchall()

    conn.close()

    candidatos = []
    for candidato in candidatos_db:
        score, motivos = calcular_score(vaga, candidato)
        candidato_dict = dict(candidato)
        candidato_dict['score'] = score
        candidato_dict['motivos'] = motivos
        candidatos.append(candidato_dict)

    candidatos.sort(key=lambda x: x['score'], reverse=True)

    return render_template(
        'candidatos.html',
        vaga=vaga,
        candidatos=candidatos,
        status_filtro=status_filtro,
        contagem_status=contagem_status,
        total_candidatos=total_candidatos
    )


@app.route('/candidato/<int:id>/status', methods=['POST'])
def atualizar_status_candidato(id):
    if 'empresa_id' not in session:
        return redirect(url_for('pagina_login'))

    novo_status = request.form.get('status')

    if not novo_status:
        flash('Selecione um status válido.', 'erro')
        return redirect(request.referrer)

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE candidatos
        SET status = ?
        WHERE id = ?
    ''', (novo_status, id))

    conn.commit()
    conn.close()

    flash('Status atualizado com sucesso!', 'sucesso')
    return redirect(request.referrer)


@app.route('/arquivo/<nome>')
def servir_arquivo(nome):
    return send_from_directory(app.config['UPLOAD_FOLDER'], nome)


@app.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    mensagem = None
    erro = None

    if request.method == 'POST':
        email = request.form.get('email')

        conn = conectar_banco()
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

    conn = conectar_banco()
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)