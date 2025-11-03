import psycopg2
from app.config import SERVERS, LOCAL_SERVERS 
from prettytable import PrettyTable
from collections import defaultdict
from datetime import timezone

def connect_to_db(servidor_id):
    config = SERVERS.get(servidor_id)
    if not config: return None
    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 5
    try:
        conn = psycopg2.connect(**connect_args)
        return conn
    except psycopg2.OperationalError:
        return None

def visualizar_alunos():
    print("\n--- Opção 5: Visualização de Matrículas (Modo Diagnóstico) ---")
    for servidor_id in LOCAL_SERVERS:
        conn = connect_to_db(servidor_id)
        if conn:
            cursor = conn.cursor()
            try:
                
                cursor.execute("""
                    SELECT 
                        m.id AS matricula_uuid, d.nome AS disciplina,
                        d.vagas_totais, m.nome_aluno, 
                        m.timestamp_matricula, m.status
                    FROM matriculas m
                    JOIN disciplinas d ON m.disciplina_id = d.id
                    WHERE m.status != 'REMOVIDA' 
                      AND (d.is_deleted IS NULL OR d.is_deleted = false)
                    ORDER BY d.nome, m.timestamp_matricula; 
                """)
                rows = cursor.fetchall()
                print(f"\n=== Todas as Matrículas (Ativas e Espera) no Servidor: {servidor_id} ===")
                if not rows:
                    print("Nenhuma matrícula encontrada nesta base de dados.")
                    continue

                disciplinas_data = defaultdict(list)
                disciplinas_vagas = {}
                for matricula_uuid, disciplina_nome, vagas, aluno, timestamp_db, status in rows:
                    disciplinas_data[disciplina_nome].append((matricula_uuid, aluno, timestamp_db, status))
                    disciplinas_vagas[disciplina_nome] = vagas

                for disciplina_nome in sorted(disciplinas_data.keys()):
                    vagas = disciplinas_vagas[disciplina_nome]
                    alunos_total = len(disciplinas_data[disciplina_nome])
                    print(f"\nDisciplina: {disciplina_nome} (Vagas Totais: {vagas}, Total de Entradas: {alunos_total})")
                    table = PrettyTable()
                    table.field_names = ["ID Matrícula (UUID)", "Aluno", "Data/Hora Matrícula", "Status Real"]
                    table.align = "l"
                    for matricula_uuid, aluno, timestamp_db, status in disciplinas_data[disciplina_nome]:
                        timestamp_utc = timestamp_db.replace(tzinfo=timezone.utc)
                        timestamp_local = timestamp_utc.astimezone(None)
                        ts_str = timestamp_local.strftime("%Y-%m-%d %H:%M:%S")
                        table.add_row([matricula_uuid, aluno, ts_str, status])
                    print(table)
            except psycopg2.Error as e:
                print(f"❌ Erro SQL ao consultar matrículas em {servidor_id}: {e}")
            finally:
                if cursor: cursor.close()
                if conn: conn.close()
        else:
            print(f"\n=== Servidor: {servidor_id} ===")
            print("❌ Servidor inacessível ou offline.")