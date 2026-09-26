// Renders a greeting and evaluates a user-supplied formula.
function showGreeting(name) {
  const box = document.getElementById("greeting");
  box.innerHTML = "<h2>Welcome, " + name + "!</h2>";
}

function calculate(formula) {
  return eval(formula);
}

const params = new URLSearchParams(window.location.search);
showGreeting(params.get("name"));
document.getElementById("result").textContent = calculate(params.get("formula"));
