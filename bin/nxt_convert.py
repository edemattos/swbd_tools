"""Convert the Switchboard corpus via the NXT XML annotations, instead of the Treebank3
format. The difference is that there's no issue of aligning the dps files etc."""
import os.path
from pathlib import Path

import plac
import fabric.api

import Treebank.PTB


def get_dfl(word, sent):
    turn = '%s%s' % (sent.speaker, sent.turnID[1:])
    dfl = [turn, '1' if word.isEdited() else '0', str(word.start_time), str(word.end_time)]
    return '|'.join(dfl)


def speechify(sent):
    for word in sent.listWords():
        if word.parent() is None or word.parent().parent() is None:
            continue
        if word.text == '?':
            word.prune()
        if word.isPunct() or word.isTrace() or word.isPartial():
            word.prune()
        word.text = word.text.lower()


def remove_repairs(sent):
    for node in sent.depthList():
        if node.label == 'EDITED':
            node.prune()


def remove_fillers(sent):
    for word in sent.listWords():
        if word.label == 'UH':
            word.prune()



def remove_prn(sent):
    for node in sent.depthList():
        if node.label != 'PRN':
            continue
        words = [w.text for w in node.listWords()]
        if words == ['you', 'know'] or words == ['i', 'mean']:
            node.prune()


def prune_empty(sent):
    for node in sent.depthList():
        if not node.listWords():
            try:
                node.prune()
            except:
                print node
                print sent
                raise


def convert_to_conllu(sents, name):
    """Run the Stanford dependency converter over the mrg file, via the temp
    files /tmp/*.mrg and /tmp/*.dep"""
    mrg_strs = []
    for sent in sents:
        if not sent.listWords():
            mrg_strs.append('(S (SYM -EMPTY-) )')
        else:
            mrg_strs.append(str(sent))
    mrg_str = u'\n'.join(mrg_strs)
    loc = '/tmp/%s.mrg' % name[:-4]
    out_loc = '/tmp/%s.dep' % name[:-4] 
    open(loc, 'w').write(mrg_str)
    cmd = 'java -cp "./*:" -Dfile.encoding=UTF-8 ' \
          'edu.stanford.nlp.trees.ud.UniversalDependenciesConverter ' \
          '-encoding UTF-8 -treeFile {mrg_loc} > {out_loc}'
    # Fabric just gives a nice context-manager for "cd" here
    with fabric.api.lcd('stanford_converter/'):
        # And a nice way to just run something --- I hate subprocess...
        fabric.api.local(cmd.format(mrg_loc=loc, out_loc=out_loc))
    return Path(out_loc).open().read()


def transfer_heads(orig_words, sent, heads, labels, upos, xpos):
    tokens = []
    wordID_to_new_idx = dict((w.wordID, i) for i, w in enumerate(sent.listWords()))
    new_idx_to_old_idx = dict((wordID_to_new_idx[token[0]], i) for i, token in
                              enumerate(orig_words) if token[0] in wordID_to_new_idx)
    for i, (wordID, text, pos, dfl, _, _) in enumerate(orig_words):
        if wordID in wordID_to_new_idx:
            head_in_new = heads[wordID_to_new_idx[wordID]]
            if head_in_new == 0:
                head = head_in_new
            else:
                head = new_idx_to_old_idx[head_in_new - 1] + 1
            label = labels[wordID_to_new_idx[wordID]]
        else:
            head = i
            label = 'erased'
        assert head >= 0

        if label != 'erased':  # recover UD v2 tags (upos) with original PTB (xpos)
            upos_, xpos_ = upos.pop(0), xpos.pop(0)
        else:
            upos_, xpos_ = pos, pos
        
        tokens.append((text, upos_, xpos_, head, label, dfl))
    return tokens


def do_section(ptb_files, out_dir, name):
    out_dir = Path(out_dir)
    conllu = out_dir.joinpath('%s.conllu' % name).open('w')
    pos = out_dir.joinpath('%s.pos' % name).open('w')
    txt = out_dir.joinpath('%s.txt' % name).open('w')

    for file_ in ptb_files:
        sents, orig_words, turns = [], [], []
        for sent in file_.children():
            speechify(sent)
            orig_words.append([(
                w.wordID, w.text, w.label, get_dfl(w, sent), sent.speaker, sent.globalID
            ) for w in sent.listWords()])
            turns.append(sent.turnID)
            remove_repairs(sent)
            remove_fillers(sent)
            remove_prn(sent)
            prune_empty(sent)
            sents.append(sent)
        conllu_strs = convert_to_conllu(sents, file_.filename)
        tok_id = 0
        for i, conllu_sent in enumerate(conllu_strs.strip().split('\n\n')):
            heads, labels, upos, xpos = read_conllu(conllu_sent)
            tokens = transfer_heads(orig_words[i], sents[i], heads, labels, upos, xpos)

            if not orig_words[i]:
                continue

            # TODO: recover untokenized surface forms for CoNLL-U text (see _PTBFile.py)
            raw_text = ' '.join([tok[0] for tok in tokens])
            dialogue_id, sent_id = orig_words[i][0][5].split('~')
            speaker_id = orig_words[i][0][4]
            
            conllu.write(u'# sent_id = %s_%s_%s\n' % (dialogue_id, speaker_id, sent_id))
            conllu.write(u'# turn_id = %s\n' % turns[i])
            conllu.write(u'# text = %s\n' % u''.join(raw_text))
            conllu.write(u'%s\n\n' % format_sent(tokens))
            pos.write(u'%s\n' % ' '.join('%s/%s' % (tok[0], tok[1]) for tok in tokens))
            txt.write(u'%s\n' % raw_text)


def read_conllu(dep_txt):
    """Get heads and labels"""
    heads, labels, upos, xpos = [], [], [], []
    for line in dep_txt.split('\n'):
        if not line.strip():
            continue
        fields = line.split()
        heads.append(int(fields[6]))
        labels.append(fields[7])
        upos.append(fields[3])
        xpos.append(fields[4])
    return heads, labels, upos, xpos


def format_sent(tokens):
    lines = []
    for i, (text, upos, xpos, head, label, dfl) in enumerate(tokens):
        # change fields from CoNLL-X to CoNLL-U format (edemattos 6/2021)
        fields = [i + 1, text, '_', upos, xpos, '_', head, label, '_', dfl]
        lines.append('\t'.join(str(f) for f in fields))
    return u'\n'.join(lines)


def main(nxt_loc, out_dir):
    corpus = Treebank.PTB.NXTSwitchboard(path=nxt_loc)
    do_section(corpus.train_files(), out_dir, 'train')
    do_section(corpus.dev_files(), out_dir, 'dev')
    do_section(corpus.dev2_files(), out_dir, 'dev2')
    do_section(corpus.eval_files(), out_dir, 'test')


if __name__ == '__main__':
    plac.call(main)
