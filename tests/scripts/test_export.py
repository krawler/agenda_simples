#!/usr/bin/env python3
"""
Teste automatizado para a rota /export
Valida: status, headers, JSON válido e tamanho do arquivo
"""
import urllib.request
import json
import sys
from pathlib import Path
from datetime import date

def test_export():
    """Testa a requisição GET /export com validações completas."""
    tests_passed = 0
    tests_failed = 0
    
    print("=" * 60)
    print("TESTE AUTOMATIZADO: GET /export")
    print("=" * 60)
    
    try:
        # 1. Fazer a requisição
        print("\n[1] Fazendo requisição GET /export...")
        url = 'http://127.0.0.1:8080/export'
        response = urllib.request.urlopen(url)
        data = response.read()
        
        # 2. Validar status HTTP
        status = response.getcode()
        print(f"    Status HTTP: {status}")
        if status == 200:
            print("    ✓ Status 200 OK")
            tests_passed += 1
        else:
            print(f"    ✗ Esperado 200, obtido {status}")
            tests_failed += 1
        
        # 3. Validar Content-Type
        content_type = response.getheader('Content-Type')
        print(f"\n[2] Content-Type: {content_type}")
        if content_type and 'application/json' in content_type:
            print("    ✓ Content-Type correto (application/json)")
            tests_passed += 1
        else:
            print(f"    ✗ Content-Type inválido: {content_type}")
            tests_failed += 1
        
        # 4. Validar Content-Disposition
        disposition = response.getheader('Content-Disposition')
        print(f"\n[3] Content-Disposition: {disposition}")
        if disposition and 'attachment' in disposition:
            print("    ✓ Content-Disposition contém 'attachment'")
            tests_passed += 1
            # Extrair nome do arquivo
            import re
            m = re.search(r'filename="([^"]+)"', disposition)
            if m:
                filename = m.group(1)
                expected_filename = f'eventos-backup-{date.today().isoformat()}.json'
                print(f"    Filename: {filename}")
                if filename == expected_filename:
                    print(f"    ✓ Nome do arquivo correto: {filename}")
                    tests_passed += 1
                else:
                    print(f"    ⚠ Nome esperado: {expected_filename}")
            else:
                print("    ⚠ Não foi possível extrair nome do arquivo")
        else:
            print(f"    ✗ Content-Disposition ausente ou inválido")
            tests_failed += 1
        
        # 5. Validar Content-Length
        content_length_header = response.getheader('Content-Length')
        print(f"\n[4] Content-Length header: {content_length_header}")
        if content_length_header:
            expected_length = int(content_length_header)
            actual_length = len(data)
            print(f"    Header diz: {expected_length} bytes")
            print(f"    Dados reais: {actual_length} bytes")
            if expected_length == actual_length:
                print("    ✓ Content-Length corresponde aos dados recebidos")
                tests_passed += 1
            else:
                print(f"    ✗ Mismatch: header={expected_length}, dados={actual_length}")
                tests_failed += 1
        else:
            print("    ✗ Content-Length header ausente")
            tests_failed += 1
        
        # 6. Validar JSON válido
        print(f"\n[5] Validando JSON...")
        try:
            eventos = json.loads(data.decode('utf-8'))
            print(f"    ✓ JSON válido (decodificado com sucesso)")
            print(f"    Tipo: {type(eventos)}")
            if isinstance(eventos, list):
                print(f"    ✓ Estrutura é uma lista (array)")
                print(f"    Quantidade de eventos: {len(eventos)}")
                tests_passed += 2
            else:
                print(f"    ✗ Esperado list, obtido {type(eventos)}")
                tests_failed += 1
        except json.JSONDecodeError as e:
            print(f"    ✗ JSON inválido: {e}")
            tests_failed += 1
        
        # 7. Salvar arquivo de teste
        print(f"\n[6] Salvando arquivo de teste...")
        test_file = Path(__file__).parent / 'export_test_result.json'
        test_file.write_bytes(data)
        print(f"    ✓ Arquivo salvo em: {test_file}")
        print(f"    Tamanho: {test_file.stat().st_size} bytes")
        tests_passed += 1
        
    except urllib.error.URLError as e:
        print(f"\n✗ ERRO na conexão: {e}")
        print(f"  Certifique-se de que o servidor está rodando em http://127.0.0.1:8080")
        tests_failed += 1
    except Exception as e:
        print(f"\n✗ ERRO inesperado: {e}")
        import traceback
        traceback.print_exc()
        tests_failed += 1
    
    # Resumo final
    print("\n" + "=" * 60)
    print(f"RESUMO: {tests_passed} ✓ {tests_failed} ✗")
    print("=" * 60)
    
    return tests_failed == 0

if __name__ == '__main__':
    success = test_export()
    sys.exit(0 if success else 1)
