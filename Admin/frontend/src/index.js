// frontend/src/index.js
import ReactDOM from 'react-dom/client';
import App from './App';

// Keep verbose calendar diagnostics available in development without exposing
// event metadata in end-user browser consoles.
if (process.env.NODE_ENV === 'production') {
  console.log = () => {};
  console.debug = () => {};
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
