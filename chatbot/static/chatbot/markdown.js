/*
 * Renderizador de Markdown pequeno e seguro para as respostas do modelo.
 *
 * Segurança: todo o texto é escapado ANTES de qualquer formatação, então nenhuma
 * tag HTML escrita pelo modelo chega a ser interpretada pelo navegador. Links só
 * são criados para endereços http(s).
 *
 * Suporta: blocos de código (```), código inline, títulos, negrito, itálico,
 * tachado, links, listas (com aninhamento), citações, tabelas e linhas horizontais.
 */
(function () {
  'use strict';

  const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const escapar = (texto) => texto.replace(/[&<>"']/g, (c) => ESCAPES[c]);

  const RE = {
    cerca: /^\s*(`{3,}|~{3,})\s*([\w+#.-]*)\s*$/,
    titulo: /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/,
    linha: /^\s{0,3}([-*_])(\s*\1){2,}\s*$/,
    citacao: /^\s{0,3}>\s?/,
    itemLista: /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/,
    separadorTabela: /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/,
  };

  /* ---------- Formatação dentro de uma linha ---------- */
  function inline(texto) {
    const guardados = [];
    const guardar = (html) => `\u0000${guardados.push(html) - 1}\u0000`;

    let s = escapar(texto);
    // Código inline primeiro, para que nada dentro dele seja formatado.
    s = s.replace(/(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)/g, (_, __, codigo) => guardar(`<code>${codigo.trim()}</code>`));
    // Links [texto](https://...)
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, rotulo, url) =>
      guardar(`<a href="${url}" target="_blank" rel="noopener noreferrer">${rotulo}</a>`));
    // Endereços soltos
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+[^\s<).,;:!?])/g, (_, antes, url) =>
      antes + guardar(`<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`));
    s = s
      .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>')
      // __negrito__ só fora de palavras, para não estragar nomes como __init__
      .replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, '$1<strong>$2</strong>')
      .replace(/(^|[^\w*])\*(?=[^\s*])([^*]*?[^\s*])\*(?!\w)/g, '$1<em>$2</em>')
      .replace(/(^|[^\w_])_(?=[^\s_])([^_]*?[^\s_])_(?!\w)/g, '$1<em>$2</em>')
      .replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>');
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => guardados[Number(i)]);
  }

  /* ---------- Blocos ---------- */
  const indentacao = (linha) => linha.match(/^\s*/)[0].replace(/\t/g, '    ').length;
  const ehVazia = (linha) => linha.trim() === '';

  function iniciaBloco(linhas, i) {
    const linha = linhas[i];
    return RE.cerca.test(linha) || RE.titulo.test(linha) || RE.linha.test(linha) ||
      RE.citacao.test(linha) || RE.itemLista.test(linha) || ehInicioDeTabela(linhas, i);
  }

  function ehInicioDeTabela(linhas, i) {
    return linhas[i].includes('|') && i + 1 < linhas.length && RE.separadorTabela.test(linhas[i + 1]);
  }

  function celulas(linha) {
    let s = linha.trim();
    if (s.startsWith('|')) s = s.slice(1);
    if (s.endsWith('|') && !s.endsWith('\\|')) s = s.slice(0, -1);
    return s.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
  }

  function blocoDeCodigo(linguagem, codigo) {
    const rotulo = linguagem ? escapar(linguagem) : 'código';
    return `<div class="bloco-codigo"><div class="bloco-codigo-topo"><span>${rotulo}</span>` +
      '<button type="button" class="copiar-codigo">Copiar</button></div>' +
      `<pre><code${linguagem ? ` data-linguagem="${escapar(linguagem)}"` : ''}>${escapar(codigo)}</code></pre></div>`;
  }

  function lista(linhas, i) {
    const primeira = linhas[i].match(RE.itemLista);
    const base = indentacao(primeira[1]);
    const ordenada = /\d/.test(primeira[2]);
    const inicio = ordenada ? parseInt(primeira[2], 10) : 1;
    const itens = [];
    let atual = null;

    while (i < linhas.length) {
      const linha = linhas[i];
      const m = linha.match(RE.itemLista);
      if (m && indentacao(m[1]) === base && /\d/.test(m[2]) === ordenada) {
        atual = [m[3]];
        itens.push(atual);
        i++;
      } else if (ehVazia(linha)) {
        // Linha em branco: a lista continua só se a próxima linha ainda fizer parte dela.
        const prox = linhas[i + 1];
        if (prox === undefined) break;
        const mProx = prox.match(RE.itemLista);
        const continua = indentacao(prox) > base ||
          (mProx && indentacao(mProx[1]) === base && /\d/.test(mProx[2]) === ordenada);
        if (!continua) break;
        atual.push('');
        i++;
      } else if (indentacao(linha) > base) {
        atual.push(linha.slice(Math.min(indentacao(linha), base + 4)));  // conteúdo aninhado
        i++;
      } else if (!iniciaBloco(linhas, i) && atual[atual.length - 1] !== '') {
        atual.push(linha.trim());  // continuação "preguiçosa" do texto do item
        i++;
      } else {
        break;
      }
    }

    const tag = ordenada ? 'ol' : 'ul';
    const atributoInicio = ordenada && inicio !== 1 ? ` start="${inicio}"` : '';
    const html = itens.map((partes) => {
      const temBlocos = partes.length > 1 && partes.slice(1).some((p) => RE.itemLista.test(p) || RE.cerca.test(p) || p === '');
      const conteudo = temBlocos ? blocos(partes.join('\n'), true) : inline(partes.join('\n')).replace(/\n/g, '<br>');
      return `<li>${conteudo}</li>`;
    }).join('');
    return { html: `<${tag}${atributoInicio}>${html}</${tag}>`, i };
  }

  function blocos(texto, dentroDeLista = false) {
    const linhas = texto.replace(/\r\n?/g, '\n').split('\n');
    const saida = [];
    let i = 0;

    while (i < linhas.length) {
      const linha = linhas[i];

      if (ehVazia(linha)) { i++; continue; }

      const cerca = linha.match(RE.cerca);
      if (cerca) {
        const marcador = cerca[1];
        const codigo = [];
        i++;
        while (i < linhas.length && !(linhas[i].trim().startsWith(marcador) && linhas[i].trim().replace(/[`~]/g, '') === '')) {
          codigo.push(linhas[i]);
          i++;
        }
        i++;  // pula a cerca de fechamento (ou o fim do texto, se o modelo esqueceu de fechar)
        saida.push(blocoDeCodigo(cerca[2], codigo.join('\n')));
        continue;
      }

      const titulo = linha.match(RE.titulo);
      if (titulo) {
        const nivel = Math.min(titulo[1].length + 2, 6);  // # vira h3: títulos grandes demais ficam ruins num balão
        saida.push(`<h${nivel}>${inline(titulo[2])}</h${nivel}>`);
        i++;
        continue;
      }

      if (RE.linha.test(linha)) { saida.push('<hr>'); i++; continue; }

      if (RE.citacao.test(linha)) {
        const citadas = [];
        while (i < linhas.length && RE.citacao.test(linhas[i])) {
          citadas.push(linhas[i].replace(RE.citacao, ''));
          i++;
        }
        saida.push(`<blockquote>${blocos(citadas.join('\n'))}</blockquote>`);
        continue;
      }

      if (RE.itemLista.test(linha)) {
        const resultado = lista(linhas, i);
        saida.push(resultado.html);
        i = resultado.i;
        continue;
      }

      if (ehInicioDeTabela(linhas, i)) {
        const cabecalho = celulas(linha);
        const alinhamentos = celulas(linhas[i + 1]).map((c) =>
          c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : '');
        const estilo = (j) => (alinhamentos[j] ? ` style="text-align:${alinhamentos[j]}"` : '');
        i += 2;
        const corpo = [];
        while (i < linhas.length && linhas[i].includes('|') && !ehVazia(linhas[i])) {
          const cel = celulas(linhas[i]);
          corpo.push('<tr>' + cabecalho.map((_, j) => `<td${estilo(j)}>${inline(cel[j] || '')}</td>`).join('') + '</tr>');
          i++;
        }
        saida.push('<div class="tabela"><table><thead><tr>' +
          cabecalho.map((c, j) => `<th${estilo(j)}>${inline(c)}</th>`).join('') +
          `</tr></thead><tbody>${corpo.join('')}</tbody></table></div>`);
        continue;
      }

      // Parágrafo: junta linhas até a próxima linha vazia ou outro tipo de bloco.
      const paragrafo = [linha.trim()];
      i++;
      while (i < linhas.length && !ehVazia(linhas[i]) && !iniciaBloco(linhas, i)) {
        paragrafo.push(linhas[i].trim());
        i++;
      }
      const html = inline(paragrafo.join('\n')).replace(/\n/g, '<br>');
      saida.push(dentroDeLista && saida.length === 0 ? html : `<p>${html}</p>`);
    }

    return saida.join('');
  }

  window.renderizarMarkdown = (texto) => blocos(String(texto || ''));
})();
