# pylint: disable=no-self-use,invalid-name
from numpy.testing import assert_almost_equal
import pytest
import torch
from torch.autograd import Variable
from torch.nn import LSTM
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from allennlp.common.checks import ConfigurationError
from allennlp.common.testing import AllenNlpTestCase
from allennlp.modules.seq2seq_encoders import PytorchSeq2SeqWrapper
from allennlp.nn.util import sort_batch_by_length, get_lengths_from_binary_sequence_mask

class TestPytorchSeq2SeqWrapper(AllenNlpTestCase):
    def test_get_dimension_is_correct(self):
        lstm = LSTM(bidirectional=True, num_layers=3, input_size=2, hidden_size=7, batch_first=True)
        encoder = PytorchSeq2SeqWrapper(lstm)
        assert encoder.get_output_dim() == 14
        assert encoder.get_input_dim() == 2
        lstm = LSTM(bidirectional=False, num_layers=3, input_size=2, hidden_size=7, batch_first=True)
        encoder = PytorchSeq2SeqWrapper(lstm)
        assert encoder.get_output_dim() == 7
        assert encoder.get_input_dim() == 2

    def test_forward_works_even_with_empty_sequences(self):
        lstm = LSTM(bidirectional=True, num_layers=3, input_size=3, hidden_size=7, batch_first=True)
        encoder = PytorchSeq2SeqWrapper(lstm)

        tensor = torch.autograd.Variable(torch.rand([5, 7, 3]))
        tensor[1, 6:, :] = 0
        tensor[2, :, :] = 0
        tensor[3, 2:, :] = 0
        tensor[4, :, :] = 0
        mask = torch.autograd.Variable(torch.ones(5, 7))
        mask[1, 6:] = 0
        mask[2, :] = 0
        mask[3, 2:] = 0
        mask[4, :] = 0

        results = encoder.forward(tensor, mask)

        for i in (0, 1, 3):
            assert not (results[i] == 0.).data.all()
        for i in (2, 4):
            assert (results[i] == 0.).data.all()

    def test_forward_pulls_out_correct_tensor_without_sequence_lengths(self):
        lstm = LSTM(bidirectional=True, num_layers=3, input_size=2, hidden_size=7, batch_first=True)
        encoder = PytorchSeq2SeqWrapper(lstm)
        input_tensor = Variable(torch.FloatTensor([[[.7, .8], [.1, 1.5]]]))
        lstm_output = lstm(input_tensor)
        encoder_output = encoder(input_tensor, None)
        assert_almost_equal(encoder_output.data.numpy(), lstm_output[0].data.numpy())

    def test_forward_pulls_out_correct_tensor_with_sequence_lengths(self):
        lstm = LSTM(bidirectional=True, num_layers=3, input_size=3, hidden_size=7, batch_first=True)
        encoder = PytorchSeq2SeqWrapper(lstm)
        tensor = torch.rand([5, 7, 3])
        tensor[1, 6:, :] = 0
        tensor[2, 4:, :] = 0
        tensor[3, 2:, :] = 0
        tensor[4, 1:, :] = 0
        mask = torch.ones(5, 7)
        mask[1, 6:] = 0
        mask[2, 4:] = 0
        mask[3, 2:] = 0
        mask[4, 1:] = 0

        input_tensor = Variable(tensor)
        mask = Variable(mask)
        sequence_lengths = get_lengths_from_binary_sequence_mask(mask)
        packed_sequence = pack_padded_sequence(input_tensor, sequence_lengths.data.tolist(), batch_first=True)
        lstm_output, _ = lstm(packed_sequence)
        encoder_output = encoder(input_tensor, mask)
        lstm_tensor, _ = pad_packed_sequence(lstm_output, batch_first=True)
        assert_almost_equal(encoder_output.data.numpy(), lstm_tensor.data.numpy())

    def test_forward_pulls_out_correct_tensor_for_unsorted_batches(self):
        lstm = LSTM(bidirectional=True, num_layers=3, input_size=3, hidden_size=7, batch_first=True)
        encoder = PytorchSeq2SeqWrapper(lstm)
        tensor = torch.rand([5, 7, 3])
        tensor[0, 3:, :] = 0
        tensor[1, 4:, :] = 0
        tensor[2, 2:, :] = 0
        tensor[3, 6:, :] = 0
        mask = torch.ones(5, 7)
        mask[0, 3:] = 0
        mask[1, 4:] = 0
        mask[2, 2:] = 0
        mask[3, 6:] = 0

        input_tensor = Variable(tensor)
        mask = Variable(mask)
        sequence_lengths = get_lengths_from_binary_sequence_mask(mask)
        sorted_inputs, sorted_sequence_lengths, restoration_indices = sort_batch_by_length(input_tensor,
                                                                                           sequence_lengths)
        packed_sequence = pack_padded_sequence(sorted_inputs,
                                               sorted_sequence_lengths.data.tolist(),
                                               batch_first=True)
        lstm_output, _ = lstm(packed_sequence)
        encoder_output = encoder(input_tensor, mask)
        lstm_tensor, _ = pad_packed_sequence(lstm_output, batch_first=True)
        assert_almost_equal(encoder_output.data.numpy(),
                            lstm_tensor.index_select(0, restoration_indices).data.numpy())

    def test_wrapper_raises_if_batch_first_is_false(self):

        with pytest.raises(ConfigurationError):
            lstm = LSTM(bidirectional=True, num_layers=3, input_size=3, hidden_size=7)
            _ = PytorchSeq2SeqWrapper(lstm)
