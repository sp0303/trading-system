import React from 'react';
import './Loader.css';

interface LoaderProps {
  text?: string;
}

const Loader: React.FC<LoaderProps> = ({ text = "Establishing Institutional Link..." }) => {
  return (
    <div className="loader-overlay">
      <div className="loader-content">
        <div className="loader-container">
          <div className="loader-ring"></div>
          <div className="loader-ring"></div>
          <div className="loader-ring"></div>
          <div className="loader-core">
            <div className="loader-pulse"></div>
          </div>
        </div>
        <div className="loader-text-container">
          <p className="loader-text">{text}</p>
          <div className="loader-shimmer"></div>
        </div>
      </div>
    </div>
  );
};

export default Loader;
