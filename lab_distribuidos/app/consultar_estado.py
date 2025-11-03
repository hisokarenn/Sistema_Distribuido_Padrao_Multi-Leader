import psycopg2
from prettytable import PrettyTable
from app.config import SERVERS, ALL_SERVERS 
from datetime import timezone

def connect_to_db(servidor_id):
    config = SERVERS.get(servidor_id)
    if not config: return None, "Configuração não encontrada."
    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 5
    try:
        conn = psycopg2.connect(**connect_args)
        return conn, None
    except psycopg2.OperationalError as e:
        return None, str(e)

def consultar_estado():
    print("\n" + "="*70)
    print("INICIANDO CONSULTA DE ESTADO DETALHADO DOS SERVIDORES")
    print("="*70)
    for servidor in ALL_SERVERS:
        tipo = SERVERS[servidor]['tipo'].upper()
        print("\n" + "="*20 + f" ESTADO DO {tipo} {servidor} " + "="*20)
        conn, erro_conexao = connect_to_db(servidor)
        if not conn:
            print(f"❌ Erro de conexão com o servidor {servidor}: {erro_conexao}")
            continue
        cursor = conn.cursor()
        try:
           
            cursor.execute("""
                SELECT id, nome, vagas_totais FROM disciplinas 
                WHERE (is_deleted IS NULL OR is_deleted = false) ORDER BY nome;
            """)
            disciplinas = cursor.fetchall()
            if not disciplinas:
                print("⚠️ Nenhuma disciplina encontrada. Verifique se o banco foi inicializado.")
                continue

            print(f"Disciplinas encontradas no {servidor}: {len(disciplinas)}")
            print("-" * 70)
            for disciplina_id, nome_disciplina, vagas_totais in disciplinas:
                
                
                cursor.execute("""
                    SELECT nome_aluno, timestamp_matricula FROM matriculas
                    WHERE disciplina_id = %s AND status != 'REMOVIDA'
                    ORDER BY timestamp_matricula;
                """, (disciplina_id,))
                matriculas = cursor.fetchall()
                
                matricula_table = PrettyTable()
                matricula_table.field_names = ["#", "Nome do Aluno", "Timestamp (H:M:S.ms)", "Status da Vaga"]
                matricula_table.align = "l"
                vagas_ocupadas = 0
                alunos_aceites = []
                
                for i, (nome, ts_db) in enumerate(matriculas):
                    posicao = i + 1
                    ts_utc = ts_db.replace(tzinfo=timezone.utc)
                    ts_local = ts_utc.astimezone(None)
                    ts_formatado = ts_local.strftime('%H:%M:%S.%f')[:-3] 
                    if i < vagas_totais:
                        vagas_ocupadas += 1
                        alunos_aceites.append(nome)
                        status = "✅ Válida"
                    else:
                        status = "❌ Conflito/Rejeitada"
                    matricula_table.add_row([posicao, nome, ts_formatado, status])

                print(f"\n[DISCIPLINA: {nome_disciplina}] | Vagas: {vagas_ocupadas}/{vagas_totais} ocupadas")
                print(matricula_table)
                resumo_alunos = ', '.join(alunos_aceites) if alunos_aceites else 'Nenhum'
                print(f"Alunos Matriculados (Válidos): {resumo_alunos}")
                print("-" * 70)
        except Exception as e:
            print(f"❌ Erro ao consultar o servidor {servidor}: {e}")
        finally:
            if cursor: cursor.close()
            if conn: conn.close()