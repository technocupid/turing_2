"""Creates the initial Excel file and static folder."""
import os
import pandas as pd


os.makedirs('static/images', exist_ok=True)


if not os.path.exists('items.xlsx'):
    df = pd.DataFrame(columns=[
        'item_id', 'title', 'description', 'category', 'price', 'stock', 'image_filename', 'created_by'
        ])
    df.to_excel('items.xlsx', index=False)
    print('Created items.xlsx')
else:
    print('items.xlsx already exists')


