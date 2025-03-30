//Задание 1
let paragraph = document.getElementById("message");
paragraph.textContent = "Добро пожаловать в JavaScript";
//Задане 2
let boxes = document.getElementsByClassName("box");
for(let i = 0; i<boxes.length; i++){
boxes[i].style.backgroundColor = "green"
}
//Задание 3
let text = document.querySelector("#text")
text.textContent = "Thragg is viltrumites king";

boxes = document.querySelectorAll(".box")
for(let i = 0; i<boxes.length; i++){
    boxes[i].style.backgroundColor = "violet"
    }
    //Задание 4
    let mark = document.querySelectorAll(".highlight")
    mark.forEach((Element)=>{Element.style.backgroundColor = "red";})
        
    
