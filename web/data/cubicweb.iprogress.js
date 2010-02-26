function ProgressBar() {
    this.budget = 100;
    this.todo = 100;
    this.done = 100;
    this.color_done = "green";
    this.color_budget = "blue";
    this.color_todo = "#cccccc"; //  grey
    this.height = 16;
    this.middle = this.height/2;
    this.radius = 4;
}

ProgressBar.prototype.draw_one_rect = function(ctx, pos, color, fill) {
    ctx.beginPath();
    ctx.lineWidth = 1;
    ctx.strokeStyle = color;
    if (fill) {
	ctx.fillStyle = color;
	ctx.fillRect(0,0,pos,this.middle*2);
    } else {
	ctx.lineWidth = 2;
	ctx.strokeStyle = "black";
	ctx.moveTo(pos,0);
	ctx.lineTo(pos,this.middle*2);
	ctx.stroke();
    }
};

ProgressBar.prototype.draw_one_circ = function(ctx, pos, color) {
    ctx.beginPath();
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    ctx.moveTo(0,this.middle);
    ctx.lineTo(pos,this.middle);
    ctx.arc(pos,this.middle,this.radius,0,Math.PI*2,true);
    ctx.stroke();
};


ProgressBar.prototype.draw_circ = function(ctx) {
    this.draw_one_circ(ctx,this.budget,this.color_budget);
    this.draw_one_circ(ctx,this.todo,this.color_todo);
    this.draw_one_circ(ctx,this.done,this.color_done);
};


ProgressBar.prototype.draw_rect = function(ctx) {
    this.draw_one_rect(ctx,this.todo,this.color_todo,true);
    this.draw_one_rect(ctx,this.done,this.color_done,true);
    this.draw_one_rect(ctx,this.budget,this.color_budget,false);
};


function draw_progressbar(cid, done, todo, budget, color) {
    var canvas = document.getElementById(cid);
    if (canvas.getContext) {
        var ctx = canvas.getContext("2d");
	var bar = new ProgressBar();
	bar.budget = budget;
	bar.todo = todo;
	bar.done = done;
        bar.color_done = color;
	bar.draw_rect(ctx);
    }
}
