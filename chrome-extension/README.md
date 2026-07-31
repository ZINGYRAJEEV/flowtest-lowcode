# FlowTest Chrome Recorder

Record clicks, fills, selects, navigations, and text assertions in **your** Chrome window, then import the JSON into FlowTest (works with Streamlit Cloud).

## Install (unpacked)

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this `chrome-extension` folder
4. Pin the **FlowTest Recorder** extension

## Record

1. Open the site you want to test (or enter a Start URL in the popup)
2. Click the extension → **Start**
3. Use the page normally; use **Assert selection** (or press **A**) for text checks
4. Click **Finish recording** in the page banner (or **Finish** in the popup)
5. **Copy JSON** or **Download**, then open FlowTest

## Import into FlowTest

1. Log in → **Test Builder**
2. Expand **Import Chrome recording**
3. Paste JSON or upload the `.json` file
4. Choose Append or Replace → **Import steps** → **Save** the test

Cloud can then **run** the saved test headlessly.
