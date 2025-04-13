## gonna use later
```js
import React, { useState, useEffect } from 'react';

function DisplayImage({ imageId }) {
  const [imgSrc, setImgSrc] = useState('');

  useEffect(() => {
    // Example fetch to get binary data, then convert to a blob URL:
    fetch(`/api/chat/image/${imageId}`)
      .then(res => res.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        setImgSrc(url);
      })
      .catch(console.error);
  }, [imageId]);

  return (
    <div>
      <img src={imgSrc} alt="Uploaded" />
    </div>
  );
}

export default DisplayImage;
```