If you eventually move this to a production server or a environment where outbound internet is strictly blocked, you can manually include the `nltk_data` folder inside your project directory and point NLTK to it:

Python

```
import os
import nltk

# Point NLTK to a folder inside your own project
data_path = os.path.join(os.getcwd(), "nltk_data_local")
nltk.data.path.append(data_path)
```

This is the ultimate "future-proof" move because it removes the dependency on NLTK's servers entirely.
