import React, { Component } from "react";
import "./App.css";
import Spinner from "react-spinkit";

class App extends Component {
  state = { status: { images: [] }, id: 0 };

  componentDidMount() {
    this.getStatus();
  }

  getStatus() {
    console.log(this.state.id);
    fetch(`http://localhost:3000/status/${this.state.id}`)
      .then(response => response.json())
      .then(data => this.setState({ status: data }));
  }

  handleStart() {
    fetch("http://localhost:3000/start", {
      method: "POST"
    })
      .then(response => response.json())
      .then(data => this.setState({ id: data.id }))
      .then(() => this.getStatus());
    this.interval = setInterval(() => this.getStatus(), 1000);
  }

  handleStop() {
    fetch("http://localhost:3000/stop", {
      method: "POST"
    }).then(() => this.getStatus());
    clearInterval(this.interval);
  }

  handleReset() {
    fetch("http://localhost:3000/clear", {
      method: "POST"
    }).then(() => this.getStatus());
  }

  render() {
    const showSpinner =
      this.state.status.isStreaming && this.state.status.images.length === 0;
    return (
      <div className="app">
        <div>
          <button className="button" onClick={() => this.handleStart()}>
            Start
          </button>
          <button className="button" onClick={() => this.handleStop()}>
            Stop
          </button>
          <button className="button" onClick={() => this.handleReset()}>
            Reset
          </button>
        </div>
        {showSpinner && (
          <div className="spinner">
            <Spinner name="cube-grid" />
          </div>
        )}
        <div className="wrapper">
          {this.state.status.images.map(image => {
            return (
              <div
                key={image.file}
                className={`image ${image.keyframe ? "keyframe" : ""}`}
              >
                <img
                  alt="frame"
                  src={`http://localhost:5000/static/${image.file}`}
                />
              </div>
            );
          })}
        </div>
      </div>
    );
  }
}

export default App;
