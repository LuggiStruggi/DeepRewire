import torch
import copy
from torch import nn
from src import SoftDEEPR, convert_to_deep_rewireable, convert_from_deep_rewireable
from src.utils import measure_sparsity, get_compressed_model_size

import torchvision
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

import matplotlib.pyplot as plt

"""
example on how to use the conversion functions
"""

# Define the neural network architecture
class FCNN(nn.Module):
    def __init__(self):
        super(FCNN, self).__init__()
        self.fc1 = nn.Linear(28 * 28, 512)
        self.fc2 = nn.Linear(512, 256)
        self.fc3 = nn.Linear(256, 10)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        x = x.view(-1, 28 * 28)  # Flatten the input tensor
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.relu(self.fc2(x))
        x = self.dropout(x)
        x = self.fc3(x)
        return x

if __name__ == '__main__':

    # Load the MNIST dataset
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5,), (0.5,))
    ])

    train_dataset = torchvision.datasets.MNIST(root='./data', train=True, download=True, transform=transform)
    test_dataset = torchvision.datasets.MNIST(root='./data', train=False, download=True, transform=transform)

    train_size = int(0.8 * len(train_dataset))
    val_size = len(train_dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(train_dataset, [train_size, val_size])

    train_loader = torch.utils.data.DataLoader(dataset=train_dataset, batch_size=64, shuffle=True)
    val_loader = torch.utils.data.DataLoader(dataset=val_dataset, batch_size=1000, shuffle=False)
    test_loader = torch.utils.data.DataLoader(dataset=test_dataset, batch_size=1000, shuffle=False)

    # Set device (use GPU if available)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Initialize the network, loss function, and optimizer
    model = FCNN()
    print(get_compressed_model_size(model))
    convert_to_deep_rewireable(model)
    model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = SoftDEEPR(model.parameters(), lr=0.05, l1=1e-5)

    # Training loop
    num_epochs = 100
    train_losses = []
    val_accuracies = []
    sparsities = []

    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            # Forward pass
            outputs = model(images)
            loss = criterion(outputs, labels)

            # Backward pass and optimization
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        train_losses.append(running_loss / len(train_loader))

        # Validation loop
        model.eval()
        correct = 0
        total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        val_accuracy = 100 * correct / total
        val_accuracies.append(val_accuracy)

        with torch.no_grad():
            sparsity_model = copy.deepcopy(model)
            convert_from_deep_rewireable(sparsity_model)
            sparsities.append(measure_sparsity(sparsity_model.parameters()))

        print(f'Epoch [{epoch + 1}/{num_epochs}], Train Loss: {train_losses[-1]:.4f}, Val Accuracy: {val_accuracies[-1]:.2f}%, Sparsity: {sparsities[-1]}')

    # Testing the model
    convert_from_deep_rewireable(model)
    print(get_compressed_model_size(model))
    sparsity = measure_sparsity(model.parameters())
    print(sparsity)
    model.eval()
    with torch.no_grad():
        correct = 0
        total = 0

        for images, labels in test_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

        print(f'Test Accuracy: {100 * correct / total:.2f}%')

    # Plotting training loss and validation accuracy
    fig, ax1 = plt.subplots()

    ax1.set_xlabel('Epochs')
    ax1.set_ylabel('Training Loss', color='tab:blue')
    ax1.plot(train_losses, label='Training Loss', color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Validation Accuracy (%)', color='tab:orange')
    ax2.plot(val_accuracies, label='Validation Accuracy', color='tab:orange')
    ax2.tick_params(axis='y', labelcolor='tab:orange')

    ax3 = ax1.twinx()
    ax3.set_ylabel('Sparsity', color='tab:green')
    ax3.plot(sparsities, label='Sparsity', color='tab:green')
    ax3.tick_params(axis='y', labelcolor='tab:green')

    ax3.spines['right'].set_position(('outward', 60))

    fig.tight_layout()
    plt.title(f'SoftDEEPR on MNIST')
    plt.show()