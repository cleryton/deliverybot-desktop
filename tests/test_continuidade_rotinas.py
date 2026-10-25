"""Agendamento resiliente com banco fictício, sem downloads nem dados da loja."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from src import atualizacoes, backups, config, privacidade, rotinas
from src.db import get_conn, init_db


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'rotinas.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    init_db()
    monkeypatch.setattr(rotinas.seguranca, 'revelar_segredo', lambda _: 'senha-ficticia-para-teste')


@pytest.mark.parametrize('falha_protecao,falha_atualizacao', [(True, False), (False, True), (True, True)])
def test_agendador_sobrevive_a_falhas_independentes(monkeypatch, caplog, falha_protecao, falha_atualizacao):
    segredo = 'cliente-segredo-que-nao-deve-aparecer'
    proteger = Mock(side_effect=[OSError(segredo) if falha_protecao else True, True])
    atualizar = Mock(side_effect=[RuntimeError(segredo) if falha_atualizacao else None, None])
    parar = Mock()
    parar.is_set.side_effect = [False, False, True]
    monkeypatch.setattr(rotinas, '_parar', parar)
    monkeypatch.setattr(rotinas, '_thread', None)
    monkeypatch.setattr(rotinas, 'executar', proteger)
    monkeypatch.setattr(atualizacoes, 'rotina', atualizar)
    rotinas.iniciar()
    rotinas._thread.join(timeout=2)
    assert not rotinas._thread.is_alive()
    assert proteger.call_count == atualizar.call_count == 2
    assert parar.wait.call_count == 2
    parar.wait.assert_called_with(60)
    assert segredo not in caplog.text
    assert 'indisponível' in caplog.text


@pytest.mark.parametrize('fuso', [timezone.utc, timezone(timedelta(hours=-3))])
def test_backup_recente_com_fuso_nao_e_repetido(banco, monkeypatch, fuso):
    instante = (datetime.now(fuso) - timedelta(hours=2)).isoformat()
    with get_conn() as conn:
        conn.execute('UPDATE rotinas SET backup_ativo=1, horas=24, ultima_copia=?, limpar=0 WHERE id=1', (instante,))
    criar = Mock(side_effect=AssertionError('Não criar cópia recente'))
    monkeypatch.setattr(backups, 'criar', criar)
    assert rotinas.executar() is True
    assert rotinas.situacao()['atrasado'] is False
    criar.assert_not_called()


@pytest.mark.parametrize('instante', ['data-invalida', '2020-01-01T00:00:00+00:00', '2020-01-01T00:00:00-03:00'])
def test_data_invalida_ou_antiga_nao_impede_tentativa_de_backup(banco, monkeypatch, instante):
    with get_conn() as conn:
        conn.execute('UPDATE rotinas SET backup_ativo=1, horas=24, ultima_copia=?, limpar=0 WHERE id=1', (instante,))
    criar = Mock(side_effect=OSError('disco ficticio indisponivel'))
    monkeypatch.setattr(backups, 'criar', criar)
    assert rotinas.situacao()['atrasado'] is True
    assert rotinas.executar() is False
    criar.assert_called_once()


@pytest.mark.parametrize('idade,fuso,executar', [(2, timezone.utc, False), (2, timezone(timedelta(hours=-3)), False), (49, timezone.utc, True), (None, timezone.utc, True)])
def test_limpeza_respeita_intervalo_com_fuso_e_recupera_data_invalida(banco, monkeypatch, idade, fuso, executar):
    instante = (datetime.now(fuso) - timedelta(hours=idade)).isoformat() if idade is not None else 'data-invalida'
    with get_conn() as conn:
        conn.execute('UPDATE rotinas SET backup_ativo=0, limpar=1, ultima_limpeza=? WHERE id=1', (instante,))
    limpar = Mock()
    monkeypatch.setattr(privacidade, 'limpar_historico', limpar)
    assert rotinas.executar() is True
    assert limpar.call_count == int(executar)


@pytest.mark.parametrize('instante', [None, '', 42, 'x' * 65, '2026-01-01T00:00:00+99:00'])
def test_datas_inesperadas_sao_tratadas_como_nao_confirmadas(instante):
    assert rotinas._instante_utc(instante) is None


def test_datas_antigas_sem_fuso_continuam_sendo_utc():
    assert rotinas._instante_utc('2026-01-01T00:00:00') == datetime(2026, 1, 1)
    assert rotinas._instante_utc('2025-12-31T21:00:00-03:00') == datetime(2026, 1, 1)
