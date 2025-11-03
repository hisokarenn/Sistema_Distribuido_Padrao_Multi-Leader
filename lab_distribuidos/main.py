try:
    from app.adicionar_disciplina import adicionar_disciplina 
    from app.remover_disciplina import remover_disciplina 
    from app.matricular import matricular_aluno_menu
    from app.visualizar_disciplinas import visualizar_disciplinas
    from app.relatorio_consolidado import gerar_relatorio 
    from app.consultar_estado import consultar_estado
    from app.remover import remover_matricula_menu 
    from app.visualizar import visualizar_alunos 
    from app.setup_database import verificar_conexao_menu 
    from app.sincronizacao import sincronizar_ao_iniciar ### NOVO ###
except ImportError as e:
    print(f"❌ ERRO GRAVE DE IMPORTAÇÃO: O módulo não foi encontrado ou a função não existe.")
    print(f"Detalhe: {e}. Verifique se a função principal existe em seu respectivo arquivo, e se app/config.py e app/__init__.py estão no lugar.")
    exit()

def exibir_menu():
    print("\n" + "="*50)
    print("SISTEMA DE GERENCIAMENTO DE DISCIPLINAS DISTRIBUÍDO")
    print("="*50)
    print("          OPERAÇÕES PRINCIPAIS")
    print("1.  Adicionar Nova Disciplina")
    print("2.  Visualizar Disciplinas Disponíveis")
    print("3.  Remover Disciplina")
    print("4.  Matricular Aluno em Disciplina")
    print("5.  Visualizar Alunos/Matrículas")
    print("6.  Remover Matrícula/Aluno")
    print("7.  Gerar Relatório Consolidado")
    print("8.  Consultar Estado Detalhado")
    print("9.  Verificar Conexões de DB")
    print("10. Forçar Sincronização Manual (Heal)") 
    print("-" * 50)
    print("0. Sair")
    print("="*50)

def main():
    
    # ### NOVO ###: Executa a sincronização uma vez ao iniciar o app
    sincronizar_ao_iniciar() 
    
    while True:
        exibir_menu()
        try:
            opcao = input("Escolha uma opção: ")
            if opcao == '1':
                print("\n-> ADICIONAR DISCIPLINA")
                adicionar_disciplina()
            elif opcao == '2':
                print("\n-> VISUALIZAR DISCIPLINAS")
                visualizar_disciplinas()
            elif opcao == '3':
                print("\n-> REMOVER DISCIPLINA")
                remover_disciplina()
            elif opcao == '4':
                print("\n-> MATRICULAR ALUNO")
                matricular_aluno_menu()
            elif opcao == '5':
                print("\n-> VISUALIZAR ALUNOS/MATRÍCULAS")
                visualizar_alunos()
            elif opcao == '6':
                print("\n-> REMOVER MATRÍCULA/ALUNO")
                remover_matricula_menu() 
            elif opcao == '7':
                print("\n-> GERAR RELATÓRIO CONSOLIDADO")
                gerar_relatorio()
            elif opcao == '8':
                print("\n-> CONSULTAR ESTADO DETALLED")
                consultar_estado()
            elif opcao == '9':
                print("\n-> VERIFICAR CONEXÕES DE DB")
                verificar_conexao_menu()
            elif opcao == '10':
                print("\n-> FORÇAR SINCRONIZAÇÃO MANUAL (HEAL)")
                sincronizar_ao_iniciar()
            elif opcao == '0':
                print("Saindo do sistema. Até logo!")
                break
            else:
                print("Opção inválida. Tente novamente.")
        except Exception as e:
            print(f"\nERRO: Ocorreu um erro durante a execução da função: {e}")
            print("Pressione Enter para continuar...")
            input()

if __name__ == "__main__":
    main()