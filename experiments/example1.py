import torch
import copy
from torch import nn
from src import DEEPR, SoftDEEPR, convert_to_deep_rewireable, convert_from_deep_rewireable
from src.utils import measure_sparsity
import matplotlib.pyplot as plt

"""
This is just an example to see if everything is basically working (converson, reconversion, optimization).
We fit a fixed input tensor X to a fixed target tensor y over 100 iterations, we plot the loss as well as the inital and final sparsity of the model.
Additionally we do SGD on a copy of the network as a baseline and also calculate that sparsity.
"""

class someFCN(nn.Module):

    def __init__(self):
        super(someFCN, self).__init__()
        self.linear1 = nn.Linear(500, 300, bias=False)
        self.linear2 = nn.Linear(300, 100, bias=False)
        self.linear3 = nn.Linear(100, 50)
        self.linear4 = nn.Linear(50, 1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.linear1(x)
        x = self.relu(x)
        x = self.linear2(x)
        x = self.relu(x)
        x = self.linear3(x)
        x = self.relu(x)
        return self.linear4(x)


if __name__ == '__main__':
    # Check if CUDA is available and set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Create models and move them to the device
    model = someFCN().to(device)
    model2 = copy.deepcopy(model).to(device)

    threshold = 1e-3
    init_sparsity = measure_sparsity(model.parameters(), threshold=threshold)
    convert_to_deep_rewireable(model, handle_biases='second_bias')
    optimizer = SoftDEEPR(model.parameters(), lr=0.05, l1=0.005)
    optimizer2 = torch.optim.SGD(model2.parameters(), lr=0.05)
    criterium = nn.MSELoss()

    # Data Tensor X and target y, moved to the device
    X = torch.rand(100, 500).to(device)
    y = torch.rand(100, 1).to(device)

    losses = []
    losses2 = []

    for epoch in range(100):

        # SoftDEEPR
        pred = model(X)
        loss = criterium(pred, y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(loss.item())

        # SGD
        pred2 = model2(X)
        loss2 = criterium(pred2, y)
        optimizer2.zero_grad()
        loss2.backward()
        optimizer2.step()
        losses2.append(loss2.item())

    convert_from_deep_rewireable(model)

    final_sparsity = measure_sparsity(model.parameters())
    final_sparsity2 = measure_sparsity(model2.parameters(), threshold=threshold)

    pred = model(X)
    loss = criterium(pred, y).detach().cpu()
    plt.plot(losses)
    plt.plot(losses2)
    plt.plot([loss.item() for l in range(len(losses))], 'r--')
    plt.xlabel("iteration")
    plt.ylabel("MSE loss")
    plt.legend(["SoftDEEPR", "SGD", "test of SoftDEEPR after converting back"])
    plt.title(f"Initial sparsity (threshold {threshold}): {init_sparsity:.2f}\n"+
              f"Final sparsity SoftDEEPR (real zeros): {final_sparsity:.2f}\n"+
              f"Final sparsity SGD (threshold {threshold}): {final_sparsity2:.2f}\n")
    plt.show()