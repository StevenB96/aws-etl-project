import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm, percentileofscore

# Set the mean and standard deviation for the normal distribution
mean = 0
std_dev = 1
data_points = 100

# Generate random numbers from a normal distribution
data = np.random.normal(mean, std_dev, data_points)

# Fit a normal distribution to the data
fit_mean, fit_std = norm.fit(data)

bins = max(10, round(data_points / 20))

# Plot the histogram of the random numbers
plt.hist(data, bins=bins, density=True, alpha=0.5, color='#007bff')

# Overlay a normal distribution curve
xmin, xmax = plt.xlim()
x = np.linspace(xmin, xmax, 100)
p = norm.pdf(x, fit_mean, fit_std)
plt.plot(x, p, 'k', linewidth=2)

# Add vertical lines to represent percentiles
percentiles = [25, 50, 75]
percentile_values = np.percentile(data, percentiles)
for percentile, value in zip(percentiles, percentile_values):
    plt.axvline(value, color='black', linestyle='dashed', linewidth=1)

# Add a vertical line to represent a specific value (e.g., x=2)
plt.axvline(0.5, color='#007bff', linestyle='solid',
            linewidth=2, label=f'Your score')

# Calculate and display the percentile of the specific value
score_percentile = percentileofscore(data, 0.5)
plt.title(f'Score Distribution')

# Add labels and title
plt.xlabel('Value')
plt.ylabel('Probability Density')

# Add legend
plt.legend()

plt.show()

# # Save the plot as a PNG in memory
# buffer = io.BytesIO()
# plt.savefig(buffer, format='png')
# buffer.seek(0)

# # Convert the image data to a base64-encoded string
# image_string = base64.b64encode(buffer.read()).decode('utf-8')

# # Close the buffer to free up resources
# buffer.close()

# return image_string, score_percentile
