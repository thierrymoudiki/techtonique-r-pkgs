# Documentation URLs for Techtonique packages

BASE_URL_DOCS = 'https://docs.techtonique.net/'

# List of R packages
R_PACKAGES = [
    'ahead',
    'bayesianrvfl',
    'bcn',
    'crossvalidation',
    'ESGtoolkit',    
    'learningmachine',
    'matern32',
    'misc',    
    'mlsauce_r',
    'nnetsauce_r',     
    'simulatetimeseries',
    'techtonique_api_r',
    'tisthemachinelearner_r',
]

PKGS_DESC = {
    'ahead': 'Probabilistic Univariate and Multivariate time series forecasting',
    'bayesianrvfl': 'Adaptive Bayesian (NON)Linear regression',
    'bcn': 'Boosted Configuration (neural) Networks for supervised learning',
    'crossvalidation': 'Cross-validation functions',
    'esgtoolkit': 'A toolkit for Monte Carlo Simulations in Finance, Economics, Insurance, Physics',
    'forecastingapi': 'Techtonique API interface',
    'learningmachine': 'Machine Learning with Explanations and Uncertainty Quantification',
    'matern32': 'Interpretable Probabilistic Kernel Ridge Regression using Matern 3/2 kernels',
    'misc': 'Miscellaneous R functions',
    'mlsauce': 'Machine learning algorithms, PORT from Python to R',
    'nnetsauce': 'Statistical/Machine Learning using Randomized and Quasi-Randomized (neural) networks, PORT from Python to R',
    'simulatetimeseries': 'Data for time series benchmarking',    
    'tisthemachinelearner': 'Lightweight interface to scikit-learn with 2 classes, Classifier and Regressor'
}

# Package names and their documentation URLs
DOC_URLS = {
    'ahead': BASE_URL_DOCS + 'ahead/',
    'bayesianrvfl': BASE_URL_DOCS + 'bayesianrvfl/',
    'bcn': BASE_URL_DOCS + 'bcn/',
    'crossvalidation': BASE_URL_DOCS + 'crossvalidation/',
    'esgtoolkit': BASE_URL_DOCS + 'ESGtoolkit/',
    'forecastingapi': BASE_URL_DOCS + 'techtonique_api_r/',
    'learningmachine': BASE_URL_DOCS + 'learningmachine/',
    'matern32': BASE_URL_DOCS + 'matern32/',
    'misc': BASE_URL_DOCS + 'misc/',    
    'mlsauce': BASE_URL_DOCS + 'mlsauce_r/',
    'nnetsauce': BASE_URL_DOCS + 'nnetsauce_r/',    
    'simulatetimeseries': BASE_URL_DOCS + 'simulatetimeseries/',    
    'tisthemachinelearner': BASE_URL_DOCS + 'tisthemachinelearner_r/'    
}
