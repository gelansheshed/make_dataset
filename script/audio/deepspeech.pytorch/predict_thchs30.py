import argparse
import sys
import time
import os
import torch
from torch.autograd import Variable

from data.data_loader import SpectrogramParser
# from decoder import GreedyDecoder, BeamCTCDecoder, Scorer, KenLMScorer
from decoder import GreedyDecoder, BeamCTCDecoder
from model import DeepSpeech
os.environ["CUDA_VISIBLE_DEVICES"]="2"

parser = argparse.ArgumentParser(description='DeepSpeech prediction')
parser.add_argument('--model_path', default='models/deepspeech_final.pth.tar',
                    help='Path to model file created by training')
parser.add_argument('--audio_path', default='audio.wav',
                    help='Audio file to predict on')
parser.add_argument('--cuda', action="store_true", help='Use cuda to test model')
parser.add_argument('--decoder', default="greedy", choices=["greedy", "beam"], type=str, help="Decoder to use")
beam_args = parser.add_argument_group("Beam Decode Options", "Configurations options for the CTC Beam Search decoder")
beam_args.add_argument('--beam_width', default=10, type=int, help='Beam width to use')
beam_args.add_argument('--lm_path', default=None, type=str, help='Path to an (optional) kenlm language model for use with beam search (req\'d with trie)')
beam_args.add_argument('--trie_path', default=None, type=str, help='Path to an (optional) trie dictionary for use with beam search (req\'d with LM)')
beam_args.add_argument('--lm_alpha', default=0.8, type=float, help='Language model weight')
beam_args.add_argument('--lm_beta1', default=1, type=float, help='Language model word bonus (all words)')
beam_args.add_argument('--lm_beta2', default=1, type=float, help='Language model word bonus (IV words)')
args = parser.parse_args()

if __name__ == '__main__':
    model = DeepSpeech.load_model(args.model_path, cuda=args.cuda)
    model.eval()

    labels = DeepSpeech.get_labels(model)
    audio_conf = DeepSpeech.get_audio_conf(model)

    if args.decoder == "beam":
        scorer = None
        if args.lm_path is not None:
            scorer = KenLMScorer(labels, args.lm_path, args.trie_path)
            scorer.set_lm_weight(args.lm_alpha)
            scorer.set_word_weight(args.lm_beta1)
            scorer.set_valid_word_weight(args.lm_beta2)
        else:
            scorer = Scorer()
        decoder = BeamCTCDecoder(labels, scorer, beam_width=args.beam_width, top_paths=1, space_index=labels.index(' '), blank_index=labels.index('_'))
    else:
        decoder = GreedyDecoder(labels, space_index=labels.index('<space>'), blank_index=labels.index('_'))

    parser = SpectrogramParser(audio_conf, normalize=True)

    t0 = time.time()
    spect = parser.parse_audio(args.audio_path).contiguous()
    spect = spect.view(1, 1, spect.size(0), spect.size(1))
    out = model(Variable(spect, volatile=True))
    out = out.transpose(0, 1)  # TxNxH
    decoded_output = decoder.decode(out.data)
    t1 = time.time()

    print(decoded_output[0])
    words = decoded_output[0].split('<space>')
    print(words)
    base_name = os.path.basename(args.audio_path)[:-4]
    print(base_name)
    fid = open(base_name+'-predict.txt','w')
    word_num = len(words)
    for word in words:
        phones = word.strip()
        content = '{'+phones+'}'
        fid.write(content)
        if word_num > 0:
            fid.write(' ')
            word_num -= 1
    fid.close()
    # print("Decoded {0:.2f} seconds of audio in {1:.2f} seconds".format(spect.size(3)*audio_conf['window_stride'], t1-t0), file=sys.stderr)

