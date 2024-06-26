import pytest
from tests.models import FCN, CNN
from deep_rewire.utils import measure_sparsity
from deep_rewire.convert import NonTrainableParameter
from deep_rewire import convert, reconvert
from torch import nn
import copy
import torch


def test_non_trainable_parameter():
    # Create a NonTrainableParameter
    param = NonTrainableParameter(torch.tensor([1.0, 2.0, 3.0]))

    # Assert that requires_grad is False
    assert param.requires_grad == False, "NonTrainableParameter should have requires_grad set to False"

    # Try setting requires_grad to True and assert it is still False
    param.requires_grad = True
    assert param.requires_grad == False, "NonTrainableParameter should not allow requires_grad to be set to True"

    # Try setting requires_grad to False and assert it is still False
    param.requires_grad = False
    assert param.requires_grad == False, "NonTrainableParameter should keep requires_grad set to False"


@pytest.mark.parametrize("model_class", [FCN, CNN])
@pytest.mark.parametrize("handle_biases", ['ignore', 'as_connections', 'second_bias'])
def test_forward_pass(model_class, handle_biases):
    model = model_class()
    convert(model, handle_biases=handle_biases)
    sample_input = torch.randn(1, *model.input_shape)
    output = model(sample_input)
    assert output.shape == (1, *model.output_shape)


@pytest.mark.parametrize("model_class", [FCN, CNN])
@pytest.mark.parametrize("handle_biases", ['ignore', 'as_connections', 'second_bias'])
def test_loss_calculation(model_class, handle_biases):
    model = model_class()
    convert(model, handle_biases=handle_biases)
    sample_input = torch.randn(1, *model.input_shape)
    sample_output = torch.randn(1, 10)
    criterion = torch.nn.MSELoss()
    output = model(sample_input)
    loss = criterion(output, sample_output)
    assert loss.item() > 0


@pytest.mark.parametrize("model_class", [FCN, CNN])
@pytest.mark.parametrize("handle_biases", ['ignore', 'as_connections', 'second_bias'])
def test_measure_sparsity(model_class, handle_biases):
    model = model_class()
    sp1 = measure_sparsity(model)
    convert(model, keep_signs=True, handle_biases=handle_biases)
    sp2 = measure_sparsity(model)
    assert sp1 == sp2
    reconvert(model)
    sp3 = measure_sparsity(model)
    assert sp2 == sp3


@pytest.mark.parametrize("model_class", [FCN, CNN])
def test_parameters(model_class):
    rewired_model = model_class()
    standard_model = copy.deepcopy(rewired_model)
    convert(rewired_model)
    a = set(rewired_model.state_dict().keys())
    b = set(standard_model.state_dict().keys())
    assert a != b
    reconvert(rewired_model)
    a = set(rewired_model.state_dict().keys())
    b = set(standard_model.state_dict().keys())
    assert a == b
    s1 = measure_sparsity(rewired_model.parameters())
    s2 = measure_sparsity(standard_model.parameters())
    assert s1 > s2


@pytest.mark.parametrize("model_class", [FCN, CNN])
@pytest.mark.parametrize("handle_biases", ['ignore', 'as_connections', 'second_bias'])
def test_reconversion(model_class, handle_biases):
    for i in range(3):
        with torch.no_grad():
            model = model_class()
            model.eval()
            convert(model, handle_biases=handle_biases)
            inpt = torch.rand((1, *model.input_shape))
            out_pre_reconversion = model(inpt)
            reconvert(model)
            out_post_reconversion = model(inpt)
        assert torch.equal(out_pre_reconversion, out_post_reconversion)


@pytest.mark.parametrize("model_class", [FCN, CNN])
@pytest.mark.parametrize("handle_biases", ['ignore', 'as_connections', 'second_bias'])
def test_conversion(model_class, handle_biases):
    for i in range(3):
        with torch.no_grad():
            model = model_class()
            model.eval()
            inpt = torch.rand((1, *model.input_shape))
            out_pre_conversion = model(inpt)
            convert(model, handle_biases=handle_biases, keep_signs=True)
            out_post_conversion = model(inpt)
        assert torch.equal(out_pre_conversion, out_post_conversion)


@pytest.mark.parametrize("model_class", [FCN, CNN])
@pytest.mark.parametrize("handle_biases", ['ignore', 'as_connections', 'second_bias'])
def test_active_probability(model_class, handle_biases):
    for s in range(11):
        connectivity = 1 - s / 10
        sparsities = []
        for i in range(10):
            with torch.no_grad():
                model = model_class()
                sp, ot = convert(model, handle_biases=handle_biases,
                        active_probability=connectivity)
                reconvert(model)
                if ot != []:
                    n_sp = sum(p.numel() for p in sp)
                    n_ot = sum(p.numel() for p in ot)
                    ratio = n_sp / (n_ot + n_sp)
                else:
                    ratio = 1
                sparsities.append(measure_sparsity(model.parameters())*ratio)
        sparsity = sum(sparsities)/len(sparsities)
        assert pytest.approx(connectivity, abs=0.01) == 1.0 - sparsity
