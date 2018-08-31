import React, { Component } from "react";
import "./App.css";
import Spinner from "react-spinkit";

class App extends Component {
  budget = 5;
  state = {
    status: { images: [] },
    id: 0,
    budget: this.budget,
    remaining: this.budget
  };

  componentDidMount() {
    this.getStatus();
  }

  updateBudget(evt) {
    const budget = evt.target.value;
    this.setState({
      budget: budget,
      remaining: this.calculateRemaining(budget)
    });
  }

  calculateRemaining(budget) {
    const numKFs = this.state.status.images
      .map(image => (image.keyframe ? 1 : 0))
      .reduce((a, b) => a + b, 0);

    return budget - numKFs;
  }

  getStatus() {
    fetch(`http://localhost:3000/status/${this.state.id}`)
      .then(response => response.json())
      .then(data => this.setState({ status: data }))
      .then(() =>
        this.setState({ remaining: this.calculateRemaining(this.state.budget) })
      );
  }

  handleStart() {
    fetch("http://localhost:3000/start", {
      method: "POST",
      body: JSON.stringify({ budget: this.state.budget })
    })
      .then(response => response.json())
      .then(data => this.setState({ id: data.id }))
      .then(() => this.getStatus())
      .catch(error => {
        console.error(error);
      });
    this.interval = setInterval(() => this.getStatus(), 500);
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
          <div className="budget">
            <div className="row">
              <div className="label">Budget</div>
              <input
                type="text"
                className="value"
                value={this.state.budget}
                onChange={evt => this.updateBudget(evt)}
              />
            </div>
            <div className="row">
              <div className="label">Remaining</div>
              <input
                className="value"
                type="text"
                value={this.state.remaining}
                readOnly
              />
            </div>
          </div>
          <div className="actions">
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
