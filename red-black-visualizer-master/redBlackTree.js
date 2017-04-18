var RedBlackTree = function(value, parent){
  this.value = value;
  if (parent) {
    this.color = "red";
  } else {
    this.color = "black";
  }
  this.left = null;
  this.right = null;
  this.parent = parent || null;
};

RedBlackTree.prototype.getGP = function() {
  if (this.parent) {
    return this.parent.parent;
  }
  return null;
};

RedBlackTree.prototype.getUnc = function() {
  if (this.getGP()) {
    if (this.getGP().right === this.parent) {
      return this.getGP().left;
    }
    if (this.getGP().left === this.parent) {
      return this.getGP().right;
    }
  }
  return null;
};

RedBlackTree.prototype.insert = function(value, atRoot){
  atRoot = atRoot || false;
  if (!atRoot && this.parent) {
    return this.parent.insert(value);
  } else {
    atRoot = true;
  }
  if (this.contains(value)) { return "Value already exists in tree."; }
  if (value < this.value) {
    if (this.left === null) {
      this.left = new RedBlackTree(value, this);
      this.left.checker();
    } else {
      this.left.insert(value, atRoot);
    }
  } else {
    if (this.right === null) {
      this.right = new RedBlackTree(value, this);
      this.right.checker();
    } else {
      this.right.insert(value, atRoot);
    }
  }

};

RedBlackTree.prototype.contains = function(value, atRoot){
  atRoot = atRoot || false;
  if (!atRoot && this.parent) {
    return this.parent.contains(value);
  } else {
    atRoot = true;
  }
  if (this.value === value) {
    return true;
  } else if (value < this.value && this.left !== null) {
    return this.left.contains(value, atRoot);
  } else if (value > this.value && this.right !== null) {
    return this.right.contains(value, atRoot);
  }
  return false;
};

RedBlackTree.prototype.depthFirstLog = function(callback, atRoot){
  atRoot = atRoot || false;
  if (!atRoot && this.parent) {
    this.parent.depthFirstLog(callback);
  } else {
    atRoot = true;
    callback(this);
    if (this.left !== null) {
     this.left.depthFirstLog(callback, atRoot);
    }
    if (this.right !== null) {
      this.right.depthFirstLog(callback, atRoot);
    }
  }
};

RedBlackTree.prototype.checker = function() {
  if (!this.parent) { this.color = "black"; }

  if (this.color === "red") {
    if (this.parent && this.parent.color === "red" && this.getUnc() && this.getUnc().color === "red") {
      this.getGP().toggleColor();
      this.parent.toggleColor();
      this.getUnc().toggleColor();
    }
    if (this.parent && this.parent.color === "red" && (this.getUnc() === null || this.getUnc().color === "black")
      && this.parent.right === this && this.getGP() && this.getGP().right === this.parent) {
      var greatGP;
      if (this.getGP().parent && this.getGP().parent.left === this.getGP()) {
        greatGP = 'right';
      } else if (this.getGP().parent && this.getGP().parent.right === this.getGP()) {
        greatGP = 'left';
      }
      this.getGP().right = null;
      if (this.parent.left) {
        this.parent.left.parent = this.getGP();
        this.getGP().right = this.parent.left;
      }
      var temp = this.getGP();
      this.parent.parent = this.getGP().parent;
      temp.parent = this.parent;

      this.parent.left = temp;
      if (this.getGP() && greatGP === 'right') {
        this.getGP().left = this.parent;
      } else if (this.getGP() && greatGP === 'left') {
        this.getGP().right = this.parent;
      }
      this.parent.left.toggleColor();
      this.parent.toggleColor();
    }
    if (this.parent && this.parent.color === "red" && (this.getUnc() === null || this.getUnc().color === "black")
      && this.parent.left === this && this.getGP() && this.getGP().right === this.parent) {
      if (this.getGP().parent && this.getGP().parent.right === this.getGP()) {
        this.getGP().parent.right = this;
      } else if (this.getGP().parent && this.getGP().parent.left === this.getGP()) {
        this.getGP().parent.left = this;
      }
      this.getGP().right = null;
      if (this.left) { this.getGP().right = this.left; }
      this.parent.left = null;
      if (this.right) { this.parent.left = this.right; }
      this.left = this.getGP();
      this.right = this.parent;
      this.parent = this.getGP().parent;
      this.left.parent = this;
      this.right.parent = this;
      if (this.left.right) {
        this.left.right.parent = this.left;
      }
      if (this.right.left) {
        this.right.left.parent = this.right;
      }
      this.toggleColor();
      this.left.toggleColor();
    }

    if (this.parent && this.parent.color === "red" && (this.getUnc() === null || this.getUnc().color === "black")
      && this.parent.left === this && this.getGP() && this.getGP().left === this.parent) {
      var greatGP;
      if (this.getGP().parent && this.getGP().parent.right === this.getGP()) {
        greatGP = 'left';
      } else if (this.getGP().parent && this.getGP().parent.left === this.getGP()) {
        greatGP = 'right';
      }
      this.getGP().left = null;
      if (this.parent.right) {
        this.parent.right.parent = this.getGP();
        this.getGP().left = this.parent.right;
      }
      var temp = this.getGP();
      this.parent.parent = this.getGP().parent;
      temp.parent = this.parent;

      this.parent.right = temp;
      if (this.getGP() && greatGP === 'left') {
        this.getGP().right = this.parent;
      } else if (this.getGP() && greatGP === 'right') {
        this.getGP().left = this.parent;
      }
      this.parent.right.toggleColor();
      this.parent.toggleColor();
    }

    if (this.parent && this.parent.color === "red" && (this.getUnc() === null || this.getUnc().color === "black")
      && this.parent.right === this && this.getGP() && this.getGP().left === this.parent) {
      if (this.getGP().parent && this.getGP().parent.right === this.getGP()) {
        this.getGP().parent.right = this;
      } else if (this.getGP().parent && this.getGP().parent.left === this.getGP()) {
        this.getGP().parent.left = this;
      }
      this.getGP().left = null;
      if (this.right) { this.getGP().left = this.right; }
      this.parent.right = null;
      if (this.left) { this.parent.right = this.left; }
      this.right = this.getGP();
      this.left = this.parent;
      this.parent = this.getGP().parent;
      this.left.parent = this;
      this.right.parent = this;
      if (this.right.left) {
        this.right.left.parent = this.right;
      }
      if (this.left.right) {
        this.left.right.parent = this.left;
      }
      this.toggleColor();
      this.right.toggleColor();
    }
  }
  if (this.parent) { this.parent.checker(); }
};

RedBlackTree.prototype.toggleColor = function() {
  if (this.color === "red") { this.color = "black"; }
  else { this.color = "red"; }
};
