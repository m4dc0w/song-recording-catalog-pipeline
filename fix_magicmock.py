with open("audio_segmentation/audio_segmentation_test.py", "r") as f:
    content = f.read()

content = content.replace("from unittest.mock import patch, mock_open", "from unittest.mock import patch, mock_open, MagicMock")

with open("audio_segmentation/audio_segmentation_test.py", "w") as f:
    f.write(content)
