import sys
from pathlib import Path
import re

# assumes each dialogue (ex. sw4519) is stored in a different txt file (in conllu format)
# because turns and sentences within turns may be out of order

split = sys.argv[1]
turn_dir = '../UD_English-NXT-turn/'
files = Path(turn_dir).rglob('%s/*.txt' % split)


def reindex(lines_list):
    sent, sents, turn_len = 0, [], 0
    for i, l in enumerate(lines_list):
        l = l.split('\t') 
        
        # keep track of individual turn constituent SUs
        if l[0] == '1':
            sent += 1
            sents.append(turn_len)
            # reset SU length
            turn_len = 0
        turn_len += 1

        # update token index
        new_idx = str(i+1)
        if l[0] != new_idx:
            l[0] = new_idx

        # the root of the first SU is the root for the entire turn
        if sent == 1 and l[7] == 'root':
            turn_root_idx = l[0]
        # update head for subsequent SUs
        elif l[7] == 'root':
            l[6] = turn_root_idx
            l[7] = 'parataxis:turn'
        else:
            # add length of previous SUs to old root to match new indices
            l[6] = str(int(l[6]) + sum(sents))

        l[1] = '+'.join(l[1].split('+')[0:2] + [new_idx])
        lines_list[i] = '\t'.join(l)
    return lines_list


for filename in sorted(files):
    dialogue = dict()
    # each file is a different dialogue
    with open(str(filename)) as f:
        # collect tokens from each constituent SUs (Sentence-like Units)
        lines = []
        for line in f:
            if line.startswith('# sent_id'):
                try:
                    doc_id, sent_id, turn_id, speaker_id = line.strip().split()[3].split('_')
                except:
                    print(line.strip().split()[3].split('_'))
                    exit()
                t_id = float(re.sub('-', '..', turn_id[1:]))
                doc = '%s_%s_%s' % (doc_id, turn_id, speaker_id)
            elif line.startswith('# text'):
                text = line.strip().split()[3:]
                for i, token in enumerate(text):
                    token = token.split('+')
                    text[i] = '%s+%s+%s' % (token[0], doc, token[2])
                text = ' '.join(text)
            elif line == '\n':
                # end of SU
                if t_id in dialogue:
                    # append SU to existing turn
                    dialogue[t_id]['text'] += '%s ' % text
                    dialogue[t_id]['lines'] += lines
                else:
                    # new turn
                    dialogue[t_id] = {'doc': doc, 'text': '%s ' % text, 'lines': lines}
                # reset tokens for new SU
                lines = []
            else:
                line = line.strip().split('\t')
                # replace token sentence info with turn
                token = line[1].split('+')
                line[1] = '%s+%s+%s' % (token[0], doc, token[2]) 
                lines.append('\t'.join(line))

    # append dialogue to final turn-based conllu file
    # make sure file is empty!
    with open('%s/en_nxt-%s.conllu' % (str(turn_dir), split), 'a') as b:
        for turn in sorted(dialogue):
            b.write('# sent_id = %s\n' % str(dialogue[turn]['doc']))
            b.write('# text =')
            for i, form in enumerate(dialogue[turn]['text'].strip().split()):
                # reindex text forms
                token = form.split('+')
                b.write(' %s+%s+%s' % (token[0], token[1], str(i + 1)))
            b.write('\n')
            # reindex tokens
            lines = reindex(dialogue[turn]['lines'])
            for line in lines:
                b.write('%s\n' % str(line))
            b.write('\n')
