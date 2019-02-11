#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import unicodedata

import MeCab
import jaconv


def is_kanji(ch):
    try:
        return 'CJK UNIFIED IDEOGRAPH' in unicodedata.name(ch) or ch in ['々', 'ヵ', 'ヶ']
    except:
        pass
    return False


def is_hiragana(ch):
    try:
        return 'HIRAGANA' in unicodedata.name(ch)
    except:
        pass
    return False


def split_okurigana_reverse(text, hiragana):
    """
      tested:
        お茶(おちゃ)
        ご無沙汰(ごぶさた)
        お子(こ)さん
    """
    yield (text[0],)
    yield from split_okurigana(text[1:], hiragana[1:])


def split_okurigana(text, hiragana):
    """ 送り仮名 processing
      tested:
         * 出会(であ)う
         * 明(あか)るい
         * 駆(か)け抜(ぬ)け
    """
    if is_hiragana(text[0]):
        yield from split_okurigana_reverse(text, hiragana)
    if all(is_kanji(_) for _ in text):
        yield text, hiragana
        return
    if not hiragana:
        return
    if not is_kanji(text[0]) and text[0] == hiragana[0]:
        return
    huri = ''
    gana = hiragana
    while gana:
        pos = text.find(gana)
        if pos > -1:
            yield text[:pos], huri
            yield (gana,)
            break
        huri += gana[0]
        gana = gana[1:]


def is_mixed_japanese(text):
    found_hiragana = False
    found_kanji_after_hiragana = False
    for i, char in enumerate(text):
        if i != 0 and not found_hiragana and not is_kanji(char):
            found_hiragana = True
            continue
        if found_hiragana and is_kanji(char):
            found_kanji_after_hiragana = True
            break
    return found_kanji_after_hiragana


def split_furigana_nbest(text):
    model = MeCab.Model()
    tagger = model.createTagger()
    lattice = model.createLattice()
    lattice.set_request_type(MeCab.MECAB_NBEST)
    lattice.set_sentence(text)
    tagger.parse(lattice)
    ret = []

    found_best = False

    for _ in range(10):
        node = lattice.bos_node()

        while node:
            if node.stat in (2, 3):
                if node.stat == 3: # EOS
                    found_best = True
                    break
                node = node.next
                continue
            origin = node.surface
            if not origin:
                node = node.next
                continue

            origin = origin.encode('utf-8')[:node.length].decode('utf-8')
            if is_mixed_japanese(origin):
                break

            node = node.next

        if found_best:
            node = lattice.bos_node()
            while node:
                if node.stat in (2, 3):
                    node = node.next
                    continue
                origin = node.surface
                if not origin:
                    node = node.next
                    continue

                origin = origin.encode('utf-8')[:node.length].decode('utf-8')

                if origin != "" and any(is_kanji(_) for _ in origin):
                    if len(node.feature.split(",")) > 7:
                        kana = node.feature.split(",")[7]
                    else:
                        kana = origin
                    hiragana = jaconv.kata2hira(kana)
                    for pair in split_okurigana(origin, hiragana):
                        ret += [pair]
                else:
                    if origin:
                        ret += [(origin,)]
                node = node.next
            break

        if not lattice.next():
            break
    return ret


def split_furigana(text):
    """ MeCab has a problem if used inside a generator ( use yield instead of return  )
    The error message is:
    ```
    SystemError: <built-in function delete_Tagger> returned a result with an error set
    ```
    It seems like MeCab has bug in releasing resource
    """
    mecab = MeCab.Tagger("-Ochasen")
    mecab.parse('') # 空でパースする必要がある
    node = mecab.parseToNode(text)
    ret = []

    while node is not None:
        # 시작/끝(BOS/EOS) 노드일 경우 넘어감 (비었음)
        if node.stat in (2, 3):
            node = node.next
            continue
        origin = node.surface # もとの単語を代入
        if not origin:
            node = node.next
            continue

        # 형태소 분리
        # 전달되는 node.length는 byte 단위임
        # UTF-8 문자일 경우 3bytes, ASCII는 1byte 씩 카운트됨
        origin = origin.encode('utf-8')[:node.length].decode('utf-8')

        if origin and is_mixed_japanese(origin):
            ret.extend(split_furigana_nbest(origin))
        # originが空のとき、漢字以外の時はふりがなを振る必要がないのでそのまま出力する
        elif origin != "" and any(is_kanji(_) for _ in origin):
            # 조회 가능한 한자어, 히라가나로 대치 가능한 문자일 경우
            if len(node.feature.split(",")) > 7:
                kana = node.feature.split(",")[7] # 読み仮名を代入
            # 영숫자, 특수문자, 카타카나, 고유명사 등
            else:
                kana = origin
            hiragana = jaconv.kata2hira(kana)
            for pair in split_okurigana(origin, hiragana):
                ret += [pair]
        else:
            if origin:
                ret += [(origin,)]
        node = node.next
    return ret


def print_html(text):
    for pair in split_furigana(text):
        if len(pair)==2:
            kanji,hira = pair
            print("<ruby><rb>{0}</rb><rt>{1}</rt></ruby>".
                    format(kanji, hira), end='')
        else:
            print(pair[0], end='')
    print('')


def print_plaintext(text):
    for pair in split_furigana(text):
        if len(pair)==2:
            kanji,hira = pair
            print("%s(%s)" % (kanji,hira), end='')
        else:
            print(pair[0], end='')
    print('')


def main():
    text = sys.argv[1]
    print_html(text)


if __name__ == '__main__':
    main()
