import React from 'react';
import './App.css';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <div className="profile-container">
          <h1>DrInTech</h1>
          <div className="profile-card">
            <div className="avatar-container">
              <div className="avatar">DIT</div>
            </div>
            <div className="info-container">
              <h2>About Me</h2>
              <p>
                I'm a technology enthusiast participating in the Pulumi Deploy and Document Challenge.
                I love exploring new technologies that make infrastructure management easier and more efficient.
              </p>
              
              <h2>Why I Find Pulumi Interesting</h2>
              <div className="pulumi-facts">
                <div className="fact-card">
                  <h3>Programming Languages</h3>
                  <p>Unlike other IaC tools, Pulumi lets me use familiar languages like Python. I like python, I get to use python.</p>
                </div>
                <div className="fact-card">
                  <h3>Modern Architecture</h3>
                  <p>Pulumi automatically stores state remotely, so I don’t have to worry about setting up and securing a backend manually.</p>
                </div>
                <div className="fact-card">
                  <h3>Multi-Cloud</h3>
                  <p>With Pulumi, I can deploy infrastructure to any cloud provider using the same workflow and concepts.</p>
                </div>
              </div>
            </div>
          </div>
          <footer>
            <p>Created for the Pulumi Deploy and Document Challenge</p>
          </footer>
        </div>
      </header>
    </div>
  );
}

export default App;